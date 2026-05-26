# pi-ai-hat

**Hailo NPU Microservice Architecture for Raspberry Pi 5**

A high-performance, fully decoupled REST API and Web UI for real-time AI inference on the **Raspberry Pi 5** with the **Hailo AI Kit** (AI HAT / AI HAT+).

The project was born out of a collaboration around running custom edge-AI models for in-field agricultural diagnosis (e.g. grapevine leaf disease detection). After hitting the limits of the IMX500 sensor's converter for non-MobileNet architectures, we moved the inference workload onto the Hailo-8L accelerator, which is far more permissive about the operators it accepts. The result is a small, reusable serving stack that any device on the local network can hit from a browser — point a webcam at the subject, snap a frame, get bounding boxes back from the NPU.

---

## Why This Architecture?

The official `hailo_platform` Python bindings need to talk directly to the PCIe kernel driver at `/dev/hailo0`. When you try to import them from inside a modern Python virtual environment (FastAPI, uv, Python 3.13, etc.), path bleeding between the venv and the system Python regularly causes the driver layer to crash or fail to initialize.

**The solution** is a decoupled microservice loop:

1. **Hardware Daemon (`hailo_daemon.py`)** — runs on the *global* system Python, binds directly to the PCIe chip, listens locally on port `8001`.
2. **FastAPI Server (`server.py`)** — runs inside an isolated venv (Python 3.13 + `uv`), listens on port `8000`, proxies image bytes to the daemon.
3. **Web UI (`index.html`)** — served by FastAPI; any device on the LAN can pick a camera, snap a photo, and render the NPU bounding boxes in the browser.

```
 Browser ──HTTP──▶ server.py (venv, :8000) ──HTTP──▶ hailo_daemon.py (system py, :8001) ──▶ /dev/hailo0
```

---

## Hardware Requirements

- Raspberry Pi 5
- Raspberry Pi AI Kit (Hailo-8L) **or** AI HAT+ (Hailo-8 / Hailo-10H)
- A USB webcam, CSI camera, or any device that exposes itself as a webcam to the browser
- Network connection to the Pi (Ethernet or Wi-Fi)

---

## Installation & Setup (Fresh Raspberry Pi OS)

These steps assume a clean install of Raspberry Pi OS (Bookworm or Trixie, 64-bit) on a Pi 5.

### 1. Install kernel headers and the Hailo driver

On modern Raspberry Pi OS releases, the kernel headers and DKMS modules must match the Pi 5's architecture.

```bash
sudo apt update
sudo apt full-upgrade -y

# Pi 5-specific kernel headers
sudo apt install -y linux-headers-rpi-2712
# Fallback if the package above is unavailable:
# sudo apt install -y linux-headers-$(uname -r)

# DKMS + Hailo master driver package
sudo apt install -y dkms hailo-all
# If you have the AI HAT+ 2 (Hailo-10H) instead, use:
# sudo apt install -y hailo-h10-all

sudo reboot
```

### 2. Verify the PCIe hardware node

After the reboot, load the kernel module and confirm the device node exists.

```bash
sudo modprobe hailo_pci
ls /dev/hailo*
# Expected output: /dev/hailo0
```

If you do not see `/dev/hailo0`, recheck the HAT seating on the PCIe connector and confirm PCIe is enabled in `/boot/firmware/config.txt` (`dtparam=pciex1`).

### 3. Clone the repository and fetch a model

```bash
git clone https://github.com/<YOUR_USER>/pi-ai-hat.git
cd pi-ai-hat

# Pre-compiled YOLOv8 nano model for Hailo-8L
wget https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.15.0/hailo8l/yolov8n.hef
```

If you are using the full Hailo-8 (not the 8L), swap `hailo8l` for `hailo8` in the URL.

### 4. Create the web virtual environment

We use [`uv`](https://github.com/astral-sh/uv) to build the isolated FastAPI environment — it's much faster than `pip` and keeps the venv cleanly separated from the system Python the Hailo driver depends on.

Python dependencies for the web layer are pinned in [`requirements.txt`](requirements.txt).

```bash
# Install uv globally if you don't have it yet
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env   # or restart your shell

# Create the venv only if it doesn't already exist, then install deps
if [ ! -d web_env ]; then
    uv venv web_env
fi
source web_env/bin/activate
uv pip install -r requirements.txt
deactivate
```

Re-running these commands is safe: `uv venv` is skipped when `web_env/` already exists, and `uv pip install -r requirements.txt` is idempotent — it will only install what's missing or out of date.

---

## Running the System

Because the architecture is decoupled, you need **two terminal sessions** (or use `tmux` / `screen`).

### Terminal 1 — Hardware Daemon

Run this **outside** of any virtual environment, using the system Python, with `sudo` so it can open `/dev/hailo0`.

```bash
cd pi-ai-hat
sudo /usr/bin/python3 hailo_daemon.py
```

Wait until you see:

```
Hailo Core Daemon listening locally on port 8001...
```

### Terminal 2 — Web Server

```bash
cd pi-ai-hat
source web_env/bin/activate
python3 server.py
```

FastAPI will start on port `8000`.

---

## Using the Interface

From any computer or phone on the same local network, open a browser and go to:

```
http://<YOUR_RASPBERRY_PI_IP>:8000/
```

Then:

1. Select your webcam (physical or virtual) from the dropdown.
2. Point the camera at the subject.
3. Click **Snap & Analyze**.

The frontend grabs the frame, proxies it through the FastAPI server to the daemon, runs inference natively on the Hailo cores, and draws the bounding boxes over the snapshot.

---

## Swapping in a Custom Model

To use your own compiled `.hef`:

1. Drop the file next to `hailo_daemon.py`.
2. Update the model path (and, if your model uses a different head, the NMS / post-processing logic) inside `hailo_daemon.py`.
3. Restart the daemon.

The web layer (`server.py`, `index.html`) is model-agnostic — it just forwards image bytes and renders whatever boxes the daemon returns.

**Training a model from scratch?** See [docs/model-export.md](docs/model-export.md) for the full pipeline: dataset layout, YOLOv8 fine-tuning, ONNX export, and `hailomz` compilation to a Hailo-8L `.hef`.

---

## Troubleshooting

- **`/dev/hailo0` does not appear** — make sure the HAT is seated, PCIe is enabled in `config.txt`, and `dkms status` shows the `hailort` module as installed.
- **`hailo_daemon.py` crashes on import** — you are almost certainly running it inside the venv. Deactivate and call `/usr/bin/python3` explicitly.
- **`server.py` cannot reach the daemon** — confirm the daemon is up on port `8001` (`ss -tlnp | grep 8001`) and that no firewall rule blocks loopback.
- **Browser shows no cameras** — most browsers only expose `getUserMedia` over `https://` or `http://localhost`. From another device, use Chrome with the Pi's IP added to `chrome://flags/#unsafely-treat-insecure-origin-as-secure`, or front the server with a reverse proxy that terminates TLS.
