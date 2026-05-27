# TODO — pi-ai-hat

Working backlog for the Hailo-on-Pi-5 serving stack. Tasks are grouped by area and ordered roughly by priority within each area.

**How to use this file**

- Pick a task, change its status from `[ ]` to `[~]` (in progress), put your name and the date next to it.
- When the work lands, flip it to `[x]`, add a one-line "Done:" note pointing at the commit hash or PR.
- Keep each task to **one logical commit per session** — if scope creeps, split it and add a new task instead of stuffing more into the original.
- Append a dated entry to the **Session Log** at the bottom whenever you sit down to work, even if you don't finish. Future-you (and Patrícia) will thank you.

Status legend: `[ ]` todo · `[~]` in progress · `[x]` done · `[!]` blocked (explain why)

---

## 1. Model & Inference (`hailo_daemon.py`)

### 1.1 Make the model path configurable
- **Status:** `[x]`
- **Why:** `TARGET_MODEL = "yolov8n.hef"` is hardcoded ([hailo_daemon.py:9](hailo_daemon.py:9)). Swapping in Patrícia's grapevine `.hef` currently means editing the source.
- **How:**
  1. Read the path from `argv[1]` with a fallback to the env var `HAILO_MODEL`, then to `"yolov8n.hef"`.
  2. `raise FileNotFoundError` with a clear message if the file is missing — don't let `HEF()` throw deep inside the SDK.
  3. Update the README "Running the System" section so the example shows `sudo /usr/bin/python3 hailo_daemon.py <path-to.hef>`.
- **Done:** _(fill in commit hash)_

### 1.2 Load class names from a sidecar file
- **Status:** `[ ]`
- **Why:** The daemon currently returns `"Class 0"`, `"Class 1"`, … ([hailo_daemon.py:55](hailo_daemon.py:55)). Useless for the UI once we have real labels.
- **How:**
  1. If a `<model_name>.labels` file (one class per line) sits next to the `.hef`, load it at startup into a list.
  2. Use `labels[class_id]` in the response; fall back to `f"Class {class_id}"` if the file is missing or the index is out of range.
  3. Ship a `yolov8n.labels` with the 80 COCO classes for the default model.
- **Done:** _(fill in commit hash)_

### 1.3 Configurable confidence threshold
- **Status:** `[ ]`
- **Why:** `0.4` is hardcoded ([hailo_daemon.py:53](hailo_daemon.py:53)). Different models / use cases need different thresholds.
- **How:** Read `HAILO_CONF_THRESHOLD` env var at startup (default `0.4`). Document in README.
- **Done:** _(fill in commit hash)_

### 1.4 Generalise the NMS parsing for non-YOLO heads
- **Status:** `[ ]`
- **Why:** The parser in [hailo_daemon.py:48-66](hailo_daemon.py:48) assumes the YOLOv8 NMS output layout (`[batch][class][box][5]`). Patrícia's MobileViT classifier will produce a single logits tensor, not boxes.
- **How:**
  1. Detect the output layer type from `hef.get_output_vstream_infos()` (NMS vs. raw tensor).
  2. If raw classifier tensor → return top-k labels with scores, no `box`.
  3. The frontend already tolerates missing boxes — keep the response shape `{status, detections: [...]}` and just omit `box` when it's a pure classifier.
- **Done:** _(fill in commit hash)_

### 1.5 Reuse the InferVStreams context across requests
- **Status:** `[ ]`
- **Why:** [hailo_daemon.py:39-41](hailo_daemon.py:39) opens and tears down the inference pipeline **per request**. That's the dominant cost on every snap.
- **How:** Move `InputVStreamParams.make` / `OutputVStreamParams.make` / `network_group.activate()` to module scope, keep the `InferVStreams` context alive for the lifetime of the daemon, and only call `.infer()` in the request handler. Make sure cleanup still happens in the `finally` block of `run_daemon`.
- **Done:** _(fill in commit hash)_

---

## 2. API & Server (`server.py`)

### 2.1 Health endpoint
- **Status:** `[ ]`
- **Why:** No way to tell from the outside whether the daemon is alive without sending an image.
- **How:** Add `GET /health` to `server.py` that does `GET http://127.0.0.1:8001/health` and returns `{"server": "ok", "daemon": "ok"|"down"}`. Add a matching `GET` handler to the daemon's `BaseHTTPRequestHandler` that returns `200 OK`.
- **Done:** _(fill in commit hash)_

### 2.2 Stream `httpx.AsyncClient` lifetime
- **Status:** `[ ]`
- **Why:** [server.py:24](server.py:24) opens a fresh `AsyncClient` per request. Cheap, but wasteful — and it makes the timeout config impossible to centralise.
- **How:** Use FastAPI's `lifespan` to create one `httpx.AsyncClient` and reuse it. Bump the timeout to something explicit (e.g. `10.0`) once inference time on real models is known.
- **Done:** _(fill in commit hash)_

### 2.3 Return proper HTTP status codes on daemon failure
- **Status:** `[ ]`
- **Why:** [server.py:32](server.py:32) returns `200` with an error JSON when the daemon is down. That breaks any non-browser client that checks `response.status_code`.
- **How:** Return `502 Bad Gateway` when the daemon is unreachable, `504` on timeout, and `500` on unhandled exceptions.
- **Done:** _(fill in commit hash)_

---

## 3. Frontend (`index.html`)

### 3.1 Show confidence in the label
- **Status:** `[ ]`
- **Why:** Bounding boxes without scores are hard to debug.
- **How:** Render `${cls} ${(conf * 100).toFixed(0)}%` above each box.
- **Done:** _(fill in commit hash)_

### 3.1b Network settings panel (hamburger menu)
- **Status:** `[x]`
- **Why:** Once the Pi is in hotspot mode there is no way for the user to get back to a normal Wi-Fi connection without SSH + scripts. A field user who needed to update firmware or credentials would be stuck.
- **How:** Add a hamburger button (⁝) fixed to the top-right of `app.html`. Opens a modal that calls `GET /network-status` and shows the current mode. In hotspot mode: SSID + password form → `POST /configure-wifi` (nmcli adds the profile, background thread switches off the AP after 2 s). In Wi-Fi client mode: "Re-enable Hotspot" button → `POST /enable-hotspot`. Three new endpoints added to `server.py`.
- **Done:** Hamburger panel, `/network-status`, `/configure-wifi`, `/enable-hotspot` all implemented. Pi hostname is returned in the connect response so the user knows where to find the device after the AP drops.

### 3.2 Continuous mode (vs. single-snap)
- **Status:** `[ ]`
- **Why:** Currently the user has to click for every frame. For field demos a 1–2 FPS live loop is more compelling.
- **How:** Add a "Live" toggle that, when on, posts a frame to `/process-frame` every N ms (default 750). Throttle so a new request doesn't fire until the previous one resolves. Stop the loop on error or when the toggle is flipped off.
- **Done:** _(fill in commit hash)_

### 3.3 HTTPS / camera-permission helper
- **Status:** `[x]`
- **Why:** `getUserMedia` won't work in Chrome/Firefox over plain `http://<pi-ip>:8000` from another device. Users hit this on first run.
- **How:** Detect `navigator.mediaDevices === undefined` on load and render a clear message with the two workarounds from the README troubleshooting section.
- **Done:** Implemented proper self-signed SSL on `server.py` and built a Captive Portal warning UI to guide the user into a full browser session with camera permissions.

---

## 4. Packaging & DevEx

### 4.1 Pin versions in `requirements.txt`
- **Status:** `[ ]`
- **Why:** The current file is unpinned — fine for a fresh install today, brittle six months from now.
- **How:** After the next clean install, run `uv pip freeze > requirements.txt` from inside `web_env` and commit the pinned result.
- **Done:** _(fill in commit hash)_

### 4.2 Systemd units for daemon + server
- **Status:** `[x]`
- **Why:** Two-terminal manual startup is fine for development, painful in the field.
- **How:** Add `deploy/hailo-daemon.service` and `deploy/pi-ai-hat-web.service`. The daemon unit runs `/usr/bin/python3 /opt/pi-ai-hat/hailo_daemon.py` as root; the web unit runs `web_env/bin/python server.py` as the `pi` user and has `Requires=hailo-daemon.service`. Document the install (`systemctl enable --now ...`) in the README.
- **Done:** `deploy/hailo-daemon.service` and `deploy/pi-ai-hat-web.service` added; `install.sh` writes them to `/etc/systemd/system/` and enables them.

### 4.3 One-shot install script
- **Status:** `[x]`
- **Why:** The README install is ~6 steps. A single `./install.sh` that runs them in order (idempotently) is what Patrícia and other non-systems folks will actually use.
- **How:** Wrap sections 1–4 of the README into `install.sh` with `set -euo pipefail`. Use `command -v uv` checks so re-runs are safe. Do **not** auto-`sudo` — print the command if root is needed.
- **Done:** `install.sh` created. Covers: apt deps, venv creation, pip install, SSL cert generation, hotspot setup, systemd unit install + enable. Idempotent (skips venv/cert if already present).

### 4.4 Zero-to-Hero configuration script
- **Status:** `[x]`
- **Why:** To make deploying new Pi units totally seamless for the field, we need a script that configures everything from zero.
- **How:** Expand the install scripts (or create a new `setup_field_pi.sh`) to automatically run the `setup_hotspot.sh` for the captive portal, install the systemd services (from 4.2), and ensure the Pi boots straight into "Hailo AI Cam" Wi-Fi mode serving the web app.
- **Done:** Covered by `install.sh` (runs hotspot + enables systemd autostart). `start.sh` / `stop.sh` added for dev iteration without touching systemd.

---

## 5. Documentation

### 5.1 Add an architecture diagram
- **Status:** `[ ]`
- **Why:** The ASCII sketch in the README gets you 70% of the way. A real diagram (PNG or SVG, committed under `docs/`) makes onboarding faster.
- **How:** Draw it in draw.io / Excalidraw, export to `docs/architecture.svg`, link from the README.
- **Done:** _(fill in commit hash)_

### 5.2 Document the custom-model export pipeline
- **Status:** `[x]` — 2026-05-27
- **Why:** Getting from PyTorch → ONNX → Hailo `.hef` is the hard part of this whole project. There's institutional knowledge in the email thread that should live in the repo.
- **How:** Add `docs/model-export.md` covering: required ONNX opset, fixed-shape export, `hailomz` compile command, calibration, drop-in to the daemon.
- **Done:** First pass landed in [docs/model-export.md](docs/model-export.md), linked from the README "Swapping in a Custom Model" section. Follow-ups once we actually compile Patrícia's grapevine model end-to-end: add the real `custom_yolov8n.yaml` to the repo, capture mAP before/after INT8 quantisation, and document any errors hit during `hailomz compile` so future runs don't repeat them.

---

## 6. Android Client (`android_client/`)

### 6.1 Persist Server URL
- **Status:** `[ ]`
- **Why:** Typing `http://192.168.1.X:8000` every time the app opens is annoying.
- **How:** Save the URL to `SharedPreferences` when a request succeeds, and load it on startup.
- **Done:** _(fill in commit hash)_

### 6.2 Handle device orientation
- **Status:** `[ ]`
- **Why:** Photos taken in portrait might be rotated incorrectly when converted to a Bitmap, causing the server boxes to mismatch or the image to look sideways.
- **How:** Read EXIF data from the captured photo or normalize rotation before drawing bounding boxes.
- **Done:** _(fill in commit hash)_

---

## Session Log

One entry per working session. Newest at the top. Keep it short: what you touched, what's next.

### Template

```
### YYYY-MM-DD — <name>
- Touched: <files / areas>
- Tasks moved: <e.g. 1.1 → done, 2.1 → in progress>
- Commits: <hash hash>
- Notes / blockers: <anything the next person needs to know>
- Next: <what you'd pick up tomorrow>
```

### 2026-05-27 — Hotspot-on-boot
- Touched: `deploy/pi-ai-hat-web.service`, `install.sh`, `start.sh`
- Tasks moved: none (behaviour tweak, no standalone task)
- Commits: _(fill in hash)_
- Notes: `pi-ai-hat-web.service` now has `ExecStartPre=-/usr/bin/nmcli connection up "Hailo AI Cam"` (the `-` prefix means "don't fail if this errors", so a Pi that hasn't run `setup_hotspot.sh` yet still boots). `start.sh` does the same before launching processes. Result: the Pi always resets to hotspot mode on every service start, regardless of what the user left it set to from the hamburger menu.
- Next: nothing new — this pairs with the network settings panel (3.1b)

### 2026-05-27 — Network settings panel
- Touched: `app.html`, `server.py`
- Tasks moved: 3.1b → done (new task, added and closed)
- Commits: _(fill in hash)_
- Notes: Hamburger button (⁝, fixed top-right) opens a settings modal. Fetches `/network-status` on open (uses `nmcli` to detect whether "Hailo AI Cam" connection is active). Hotspot state shows SSID + password form with show/hide toggle; submitting calls `/configure-wifi` which adds an NM profile then switches off the AP in a background thread after 2 s (so the HTTP response goes out first). Wi-Fi state shows "Re-enable Hotspot" which calls `/enable-hotspot`. Connect response includes `hostname.local` so user knows where to find the Pi after disconnecting from the AP. Clicking the backdrop or × closes the panel.
- Next: 3.2 (continuous/live mode)

### 2026-05-27 — Install & service scripts
- Touched: `install.sh` (new), `start.sh` (new), `stop.sh` (new), `deploy/hailo-daemon.service` (new), `deploy/pi-ai-hat-web.service` (new), `TODO.md`
- Tasks moved: 4.2 → done, 4.3 → done, 4.4 → done
- Commits: _(fill in hash)_
- Notes: `install.sh` is the one-shot zero-to-hero script (apt → venv → pip → SSL cert → hotspot → systemd). Venv is created as `web_env/`. `start.sh`/`stop.sh` are for dev iteration — they stop any live systemd units first to avoid port conflicts, then run both processes in the background with logs under `logs/`. The `deploy/` service files use `/opt/pi-ai-hat` as the install path; `install.sh` writes them with the actual runtime path resolved from `$BASH_SOURCE`.
- Next: 4.1 (pin requirements.txt after a clean install into web_env)

### 2026-05-27 — Dynamic Model Loading
- Touched: `server.py`, `hailo_daemon.py`, `index.html`
- Tasks moved: 1.1 Make the model path configurable -> done
- Commits: _(fill in hash)_
- Notes: Implemented dynamic model reloading via the web UI. Added a `models/` directory and a `/models` endpoint in `server.py` to list `.hef` files. The UI now populates a dropdown with available models and sends the selection as form data to `/process-frame`. `hailo_daemon.py` was refactored to read the `X-Model` header, intelligently releasing the Hailo `VDevice` hardware and loading the newly requested `.hef` model on-the-fly.
- Next: Model labels sidecar file.

### 2026-05-27 — Captive Portal & AP Setup
- Touched: `server.py`, `setup_hotspot.sh` (new)
- Tasks moved: none
- Commits: _(fill in hash)_
- Notes: Configured the Pi to act as a Wi-Fi Access Point using NetworkManager (`setup_hotspot.sh`). Modified `server.py` to run on HTTPS (port 443) using a self-signed certificate, with a background HTTP redirect server on port 80. Added a catch-all route to intercept captive portal connectivity checks so phones automatically load the web app when connecting to the 'Hailo AI Cam' Wi-Fi.
- Next: Follow up with systemd integration to ensure `server.py` runs automatically on boot with root privileges.

### 2026-05-27 — Android Client
- Touched: `android_client/`, `docs/android_build_instructions.md`, `README.md`, `TODO.md`
- Tasks moved: none — Android backlog seeded
- Commits: _(fill in hash)_
- Notes: Created a native Android client using Kotlin + OkHttp to interface with the server. Avoided CameraX by using standard `MediaStore.ACTION_IMAGE_CAPTURE`. App takes a picture, uploads to `/process-frame`, and draws the JSON response boxes onto the Bitmap. Added build instructions to the docs.
- Next: 6.1 (Persist Server URL)

### 2026-05-27 — model-export guide
- Touched: `docs/model-export.md` (new), `README.md` (link added in "Swapping in a Custom Model"), `TODO.md` (5.2 closed)
- Tasks moved: 5.2 → done
- Commits: _(fill in)_
- Notes: Guide covers dataset layout → YOLOv8 fine-tune → ONNX export at opset 11 → `hailomz compile --hw-arch hailo8l` → drop-in to the daemon. Includes a sanity-check checklist and notes on the three most common `hailomz` failures. Cross-links to TODO 1.1 / 1.2 since the "edit `TARGET_MODEL` and `CLASS_NAMES` by hand" steps will go away once those land.
- Next: 1.1 (configurable model path), so the model-export guide's "edit line 10" step becomes a CLI argument instead.

### 2026-05-27 — initial TODO drafted
- Touched: `TODO.md` (new), `README.md`, `requirements.txt`
- Tasks moved: none — backlog seeded
- Commits: _(fill in)_
- Notes: Backlog drawn from a code read of `hailo_daemon.py` / `server.py` / `index.html` plus the Edge-NN discussion thread that motivated the project (Hailo path chosen after IMX500 converter rejected `timm` MobileViT). Default model is still `yolov8n.hef`; Patrícia's grapevine `.hef` is not yet in-repo — tasks 1.1, 1.2 and 1.4 are the prerequisites for dropping it in cleanly.
- Next: 1.1 (configurable model path) — smallest, unblocks the rest.
