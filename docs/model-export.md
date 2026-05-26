# Exporting a Custom Model for the Hailo-8L

This guide walks through training a custom object-detection model and compiling it into a Hailo `.hef` file that can be dropped into [`hailo_daemon.py`](../hailo_daemon.py).

The running example is the **grapevine leaf disease** use case that motivated this project — 5 classes, YOLOv8-nano backbone — but the same pipeline works for any YOLOv8 dataset.

> **Where this runs:** Steps 1–2 happen on a **workstation with an NVIDIA GPU** (training is far too slow on the Pi). Step 3 needs a machine with the **Hailo Dataflow Compiler / Software Suite** installed (Linux x86_64; Hailo does not ship the compiler for ARM). Step 4 is the only step that touches the Pi 5.

---

## Step 1 — Format the dataset for YOLOv8

YOLOv8 expects the standard YOLO directory layout:

```
grapevine_dataset/
├── dataset.yaml
├── train/
│   ├── images/   (photo1.jpg, photo2.jpg, ...)
│   └── labels/   (photo1.txt, photo2.txt, ...)
└── val/
    ├── images/   (validation photos)
    └── labels/   (validation labels)
```

Each `*.txt` label file holds one row per bounding box:

```
<class_id> <x_center> <y_center> <width> <height>
```

…with all coordinates **normalised to [0, 1]** relative to the image. Use a tool like [Roboflow](https://roboflow.com/), [CVAT](https://www.cvat.ai/), or [LabelImg](https://github.com/HumanSignal/labelImg) to produce them.

Then write `dataset.yaml` next to the `train/` and `val/` folders:

```yaml
path: /absolute/path/to/grapevine_dataset
train: train/images
val:   val/images

names:
  0: Black_Rot
  1: Esca
  2: Leaf_Blight
  3: Downy_Mildew
  4: Powdery_Mildew
```

`path` **must be absolute** — Ultralytics resolves the `train`/`val` paths relative to it.

---

## Step 2 — Fine-tune YOLOv8 and export to ONNX

On the GPU workstation:

```bash
pip install ultralytics
```

Then a minimal training script:

```python
from ultralytics import YOLO

# Baseline pretrained on COCO
model = YOLO("yolov8n.pt")

# Fine-tune on the grapevine dataset
model.train(
    data="dataset.yaml",
    epochs=100,
    imgsz=640,
)

# Export to ONNX — required by the Hailo compiler
model.export(format="onnx", opset=11)
```

This produces `yolov8n.onnx` in the run directory (typically `runs/detect/train/weights/`).

**Why these flags matter for Hailo:**

- `opset=11` — the Hailo Dataflow Compiler is conservative about ONNX opsets. 11 is the safe default; newer opsets occasionally introduce ops the compiler refuses.
- `imgsz=640` — keep the export shape **fixed**. Dynamic shapes are a common reason custom models fail at the Hailo parsing stage.
- Stick with the nano (`yolov8n`) backbone for the Hailo-8L. The full `yolov8s/m/l` variants compile but use more of the chip's slice budget and run slower.

> **Side note on why we use YOLOv8 here instead of MobileViT:** the IMX500's converter rejected `timm`'s MobileViT graph because of the patch-reshape / transformer operations. The Hailo-8L is much more permissive, but **convolution-heavy architectures still compile most reliably** — YOLOv8, MobileNetV2/V3, and EfficientNet-Lite are all safe choices.

---

## Step 3 — Compile with `hailomz`

Move the `.onnx` file to the machine where the **Hailo Software Suite** is installed. The Hailo Model Zoo ships a single command — `hailomz` — that handles graph parsing, INT8 quantisation, and hardware mapping in one shot.

```bash
hailomz compile yolov8n \
  --ckpt yolov8n.onnx \
  --calib-path /path/to/grapevine_dataset/train/images/ \
  --yaml custom_yolov8n.yaml \
  --hw-arch hailo8l
```

What each flag does:

| Flag | Purpose |
|------|---------|
| `yolov8n` | Selects the **architecture template** from the Hailo Model Zoo. The template tells the compiler about the YOLOv8 head, anchors, and NMS layout — so the daemon's existing parser still applies. |
| `--ckpt` | Path to your fine-tuned ONNX file. |
| `--calib-path` | A folder of representative images (a few hundred from your training set is plenty). The compiler runs them through the model to measure activation ranges, then quantises FP32 → INT8 without measurable accuracy loss. |
| `--yaml` | Custom config — usually a copy of the Model Zoo's `yolov8n.yaml` with `num_classes` and your class names patched in. |
| `--hw-arch hailo8l` | Targets the Hailo-8L on the AI Kit. Use `hailo8` for the full Hailo-8, or `hailo10h` for the AI HAT+ 2. |

The output is a single file: `yolov8n.hef`. Rename it to something meaningful (e.g. `grapevine_yolov8n.hef`) before moving on.

**Common failures at this stage:**

- *"Unsupported operator"* — almost always means the ONNX export used an opset or op the compiler doesn't recognise. Re-export with `opset=11` and `do_constant_folding=True`.
- *"Calibration failed"* — usually too few calibration images, or images that don't match the input size. Use ≥ 256 images at the same `imgsz` you trained with.
- *"Quantisation accuracy drop"* — increase the calibration set, or switch the YAML's quantisation level to `optimization_level: 2`.

---

## Step 4 — Drop the `.hef` into the daemon

On the Pi 5:

1. Copy the compiled file into the repo root next to [`hailo_daemon.py`](../hailo_daemon.py):

   ```bash
   scp grapevine_yolov8n.hef pi@<RPI_IP>:~/pi-ai-hat/
   ```

2. Point the daemon at it. In [`hailo_daemon.py`](../hailo_daemon.py):

   ```python
   TARGET_MODEL = "grapevine_yolov8n.hef"
   ```

   _(Once [TODO 1.1](../TODO.md#11-make-the-model-path-configurable) lands, you'll be able to pass this as an argument instead of editing the source.)_

3. Update the class-name mapping. Today the daemon returns `"Class 0"`, `"Class 1"`, … — replace that with your real labels:

   ```python
   CLASS_NAMES = [
       "Black_Rot",
       "Esca",
       "Leaf_Blight",
       "Downy_Mildew",
       "Powdery_Mildew",
   ]
   # then in the response builder:
   "class": CLASS_NAMES[class_id]
   ```

   _(Tracked in [TODO 1.2](../TODO.md#12-load-class-names-from-a-sidecar-file): the better long-term fix is a sidecar `*.labels` file so the daemon doesn't need a code change per model.)_

4. Restart the daemon:

   ```bash
   sudo /usr/bin/python3 hailo_daemon.py
   ```

5. Open the web UI, point the camera at a leaf, hit **Snap & Analyze**. The boxes that come back are now your custom classes.

---

## Sanity-check checklist before compilation

- [ ] `dataset.yaml` `path` is **absolute**.
- [ ] `train/images/` and `train/labels/` have matching filenames (`leaf01.jpg` ↔ `leaf01.txt`).
- [ ] Validation set is held out — not duplicated from `train/`.
- [ ] ONNX exported with `opset=11` and a **fixed** input shape.
- [ ] Calibration set has ≥ 256 images at the same resolution as training.
- [ ] `--hw-arch` matches the actual board (`hailo8l` for the AI Kit on a Pi 5).
