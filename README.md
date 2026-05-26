# pi-ai-hat

# Hailo NPU Microservice Architecture for Raspberry Pi 5

A high-performance, fully decoupled REST API and Web UI for real-time AI inference using the **Raspberry Pi 5** and the **Hailo AI Kit**.

## Why This Architecture?
The official `hailo_platform` Python bindings must communicate with the physical PCIe kernel drivers (`/dev/hailo0`). When attempting to build modern web APIs (like FastAPI) inside isolated Python virtual environments, system path bleeding often causes the hardware drivers to crash or fail to initialize.

**The Solution:** A decoupled microservice loop.
1. **The Hardware Daemon (`hailo_daemon.py`):** Runs natively on the global system Python loop, binding directly to the PCIe chip and listening internally on port 8001.
2. **The FastAPI Server (`server.py`):** Runs safely inside a modern, isolated Python virtual environment (e.g., Python 3.13), listening on port 8000 and proxying image bytes to the daemon.
3. **The Web UI (`index.html`):** Served directly by FastAPI, allowing any device on the network to select a camera, snap a photo, and render NPU bounding boxes natively in the browser.

---

## Installation & Setup (Fresh Raspberry Pi OS)

### 1. Install Kernel Headers and the Hailo Driver
On modern Raspberry Pi OS releases (like Debian Trixie), the kernel headers and DKMS modules must match your specific architecture.

```bash
# Update system repositories
sudo apt update

# Install Pi 5 specific kernel headers
sudo apt install linux-headers-rpi-2712 -y
# (Fallback: sudo apt install linux-headers-$(uname -r) -y)

# Install DKMS and the Hailo Master Driver Package
sudo apt install dkms hailo-all -y
# Note: If using the newer AI HAT+ 2 (Hailo-10H), use `hailo-h10-all` instead.

2. Verify the PCIe Hardware Node
Once installed, load the module into the kernel and verify the physical device node exists.

Bash
sudo modprobe hailo_pci
ls /dev/hailo*
(You should see /dev/hailo0 output in the terminal. If you do, your hardware is ready!)

3. Clone the Repository & Fetch the Model
Clone this repository and download a pre-compiled YOLOv8 nano .hef model from the official AWS S3 storage buckets.

Bash
git clone <YOUR_REPO_URL>
cd <YOUR_REPO_NAME>

# Download the compiled Hailo-8L model
wget [https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.15.0/hailo8l/yolov8n.hef](https://hailo-model-zoo.s3.eu-west-2.amazonaws.com/ModelZoo/Compiled/v2.15.0/hailo8l/yolov8n.hef)
4. Create the Web Virtual Environment
We use uv (a blazing fast Python package manager) to build the isolated web server environment.

Bash
# Install uv globally if you haven't yet
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh

# Create a clean virtual environment and activate it
uv venv web_env
source web_env/bin/activate

# Install the required web packages
uv pip install fastapi uvicorn httpx python-multipart
Running the System
Because this is a decoupled architecture, you need to run two separate terminal instances (or use a tool like tmux / screen).

Terminal 1: Start the Hardware Daemon
This script must be run outside of any virtual environments using the global Python binary and sudo (to grant direct read/write access to the /dev/hailo0 block).

Bash
cd <YOUR_REPO_NAME>
sudo /usr/bin/python3 hailo_daemon.py
(Wait until it prints: Hailo Core Daemon listening locally on port 8001...)

Terminal 2: Start the Web Server
Open a second terminal, enter your isolated web environment, and boot up FastAPI.

Bash
cd <YOUR_REPO_NAME>
source web_env/bin/activate
python3 server.py
Using the Interface
Once both services are running, step away from the Pi and open a web browser on any computer connected to the same local network.

Navigate to:

Plaintext
http://<YOUR_RASPBERRY_PI_IP>:8000/
Select your desired physical webcam or virtual camera from the dropdown list.

Point the camera at your subject.

Click Snap & Analyze.

The frontend will grab the frame, proxy it through the API, execute it natively on the Hailo-8L cores, and draw the bounding boxes over your snapshot
