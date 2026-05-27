## Hailo NPU Microservice Architecture for Raspberry Pi 5

A REST API and Web UI for real-time AI inference on the **Raspberry Pi 5** with the **Hailo AI Kit** (AI HAT / AI HAT+).

The project is a collaboration between IDeTIC, ULPGC, Spain, and IT Aveiro, UniAve, Portugal.

The idea is to have hardware running custom edge-AI models for in-field agricultural diagnosis (e.g. grapevine leaf disease detection). The inference workload is done by the Hailo-8L accelerator, which is fast and flexible. The result is a small, reusable serving stack that any device on the local network can hit from a browser. A webcam or phone can capture the subject, snap a frame, and get the result from the NPU.

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

### 1. Clone the repository and fetch a model

```bash
git clone https://github.com/inventor-loco/pi-ai-hat.git
cd pi-ai-hat

# Pre-compiled YOLOv8 nano model for Hailo-8L
wget https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.15.0/hailo8l/yolov8n.hef -P models/
```

If you are using the full Hailo-8 (not the 8L), swap `hailo8l` for `hailo8` in the URL.

### 2. Run the install script (twice — a reboot is required in the middle)

`install.sh` handles everything: kernel headers, Hailo driver, Python venv, SSL certificate, Wi-Fi hotspot, and systemd autostart.

**First run** — installs the Hailo driver and prompts for a reboot:

```bash
sudo bash install.sh
sudo reboot
```

**Second run** — completes the setup after the driver is loaded:

```bash
cd pi-ai-hat
sudo bash install.sh
```

That's it. Both services come up automatically on every subsequent boot.

> **If `/dev/hailo0` never appears after reboot:** recheck the HAT seating on the PCIe connector and confirm PCIe is enabled in `/boot/firmware/config.txt` (`dtparam=pciex1`). Then run `sudo modprobe hailo_pci && ls /dev/hailo*` to verify.

> **AI HAT+ 2 (Hailo-10H):** edit the `apt-get install` line in `install.sh` and replace `hailo-all` with `hailo-h10-all` before running.

<details>
<summary>Manual venv setup (optional, if you are not using install.sh)</summary>

```bash
# Install uv if you don't have it
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

if [ ! -d web_env ]; then
    uv venv web_env
fi
source web_env/bin/activate
uv pip install -r requirements.txt
deactivate
```
</details>

---

## Running the System

### Automated (recommended)

After `install.sh`, both services are managed by systemd and **start automatically on every boot** — no manual steps needed.

Check that everything came up:

```bash
systemctl status hailo-daemon pi-ai-hat-web
```

Watch live logs:

```bash
journalctl -fu hailo-daemon -fu pi-ai-hat-web
```

### Development / iteration

During development, use the included scripts to restart quickly without touching systemd:

```bash
# Stop everything (graceful kill by PID, then pkill fallback)
sudo bash stop.sh

# ... edit server.py or hailo_daemon.py ...

# Restart both services in the background
sudo bash start.sh

# Tail logs from both processes
tail -f logs/hailo_daemon.log logs/server.log
```

`start.sh` automatically stops any live systemd-managed instance first, so there are no port conflicts.

### Manual (two terminals, no install script)

**Terminal 1 — Hardware Daemon**

Run **outside** any virtual environment using the system Python:

```bash
cd pi-ai-hat
sudo /usr/bin/python3 hailo_daemon.py
```

Wait until you see: `Hailo Core Daemon listening locally on port 8001...`

**Terminal 2 — Web Server**

```bash
cd pi-ai-hat
sudo ./web_env/bin/python server.py
```

> **Note:** `server.py` must run as root because it binds to ports `80` and `443`. It generates a self-signed SSL certificate automatically on first run.

---

## Using the Interface

### Web UI (Via Wi-Fi or Local IP)
From any computer or phone on the same local network, open a browser and go to:

```
https://<YOUR_RASPBERRY_PI_IP>/app.html
```

*(You must click "Advanced -> Proceed" to bypass the self-signed certificate warning the first time).*

Then:

1. Select your webcam (physical or virtual) from the dropdown.
2. Point the camera at the subject.
3. Click **Snap & Analyze**.

The frontend grabs the frame, proxies it through the FastAPI server to the daemon, runs inference natively on the Hailo cores, and draws the bounding boxes over the snapshot.

### Captive Portal (Headless Wi-Fi)
`install.sh` configures the hotspot automatically. If you need to set it up manually:

```bash
sudo bash setup_hotspot.sh
```

Once the hotspot is active:
1. Connect your phone to the **"Hailo AI Cam"** Wi-Fi network.
2. The Captive Portal landing page (`index.html`) will automatically pop up.
3. Tap the link to open the main web app (`app.html`) in your full browser.

### Network Settings (hamburger menu ☰)

> **Default behaviour:** every time the services start (on boot or via `start.sh`) the Pi automatically activates the "Hailo AI Cam" hotspot, so it is always in field mode out of the box.



The web app has a settings panel accessible from the **☰ button** in the top-right corner. It lets you switch the Pi between hotspot and Wi-Fi client mode without any SSH or command-line access.

| Current mode | What you see | What it does |
|---|---|---|
| Hotspot active | SSID + password form | Connects Pi to a Wi-Fi router and exits AP mode |
| Wi-Fi connected | "Re-enable Hotspot" button | Switches back to AP / field mode |

After connecting to a Wi-Fi network, the Pi leaves the hotspot in ~2 seconds. The panel tells you the hostname (e.g. `raspberrypi.local`) to find the Pi on the new network.

### Android Native App
If you prefer a native mobile experience, the `android_client/` directory contains a fully functional Android application built in Kotlin. It uses the phone's native camera to take high-quality photos and sends them to the Hailo server for inference.

See the **[Android Build Instructions](docs/android_build_instructions.md)** for details on how to build and deploy the APK to your phone.

---

## Swapping in a Custom Model

To use your own compiled `.hef`:

1. Drop the `.hef` file into the `models/` folder.
2. Open the web app. The UI will automatically discover your model and list it in the "Select Model" dropdown! 
3. When you take a picture, the daemon will dynamically switch contexts and load your newly selected model directly into the Hailo NPU.

**Training a model from scratch?** See [docs/model-export.md](docs/model-export.md) for the full pipeline: dataset layout, YOLOv8 fine-tuning, ONNX export, and `hailomz` compilation to a Hailo-8L `.hef`.

---

## Troubleshooting

- **`/dev/hailo0` does not appear** — make sure the HAT is seated, PCIe is enabled in `config.txt`, and `dkms status` shows the `hailort` module as installed.
- **`hailo_daemon.py` crashes on import** — you are almost certainly running it inside the venv. Deactivate and call `/usr/bin/python3` explicitly.
- **`server.py` cannot reach the daemon** — confirm the daemon is up on port `8001` (`ss -tlnp | grep 8001`) and that no firewall rule blocks loopback.
- **Browser blocks the camera** — Because we are using a self-signed HTTPS certificate, you must click "Advanced -> Proceed" when loading the app. If you are inside the Wi-Fi captive portal popup on your phone, you must open the page in your full browser (Chrome/Safari) to grant camera permissions.
- **Pi is stuck in hotspot mode and needs internet access** — Open the web app, tap ☰ (top-right), enter your Wi-Fi network name and password, and press **Connect to Wi-Fi**. The Pi will leave the hotspot and join your network. When you are done, use the same menu to re-enable the hotspot. If you cannot reach the web app, connect the Pi via Ethernet — the hotspot only occupies `wlan0` so `eth0` is always free.
