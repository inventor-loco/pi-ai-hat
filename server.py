from fastapi import FastAPI, File, UploadFile, Request, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
import httpx
import subprocess
import threading
import socket

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
async def serve_index():
    # Serves the captive portal landing page
    return FileResponse("index.html")

@app.get("/app.html")
async def serve_app():
    # Serves the actual AI camera app
    return FileResponse("app.html")

@app.get("/models")
async def list_models():
    import os
    models_dir = os.path.join(os.path.dirname(__file__), 'models')
    os.makedirs(models_dir, exist_ok=True)
    files = [f for f in os.listdir(models_dir) if f.endswith(".hef")]
    return {"models": files}

@app.post("/process-frame")
async def process_frame(file: UploadFile = File(...), model: str = Form(None)):
    img_bytes = await file.read()
    
    headers = {}
    if model:
        headers["X-Model"] = model

    async with httpx.AsyncClient() as client:
        try:
            daemon_response = await client.post(
                "http://127.0.0.1:8001/",
                content=img_bytes,
                headers=headers,
                timeout=5.0
            )
            if daemon_response.status_code != 200:
                return {"status": "error", "message": f"Daemon Error: {daemon_response.status_code}"}
            return daemon_response.json()
        except httpx.ConnectError:
            return {"status": "error", "message": "Hailo daemon offline on port 8001."}
        except Exception as e:
            return {"status": "error", "message": f"Proxy crash: {str(e)}"}

@app.get("/network-status")
async def network_status():
    hostname = socket.gethostname()
    try:
        result = subprocess.run(
            ["nmcli", "-t", "-f", "NAME", "connection", "show", "--active"],
            capture_output=True, text=True, timeout=5
        )
        hotspot_active = "Hailo AI Cam" in result.stdout
        mode = "hotspot" if hotspot_active else "wifi"
    except Exception:
        mode = "unknown"
    return {"mode": mode, "hostname": hostname}


@app.post("/configure-wifi")
async def configure_wifi(ssid: str = Form(...), password: str = Form(...)):
    hostname = socket.gethostname()

    # Remove any existing profile with the same name so re-configuration works cleanly.
    subprocess.run(["nmcli", "connection", "delete", ssid], capture_output=True)

    try:
        subprocess.run([
            "nmcli", "connection", "add",
            "type", "wifi", "ifname", "wlan0",
            "con-name", ssid, "ssid", ssid,
            "wifi-sec.key-mgmt", "wpa-psk",
            "wifi-sec.psk", password,
            "autoconnect", "yes"
        ], check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError:
        return {"status": "error", "message": "Failed to add Wi-Fi connection — check the credentials and try again."}

    def _switch():
        import time
        time.sleep(2)
        subprocess.run(["nmcli", "connection", "modify", "Hailo AI Cam", "connection.autoconnect", "no"], capture_output=True)
        subprocess.run(["nmcli", "connection", "down", "Hailo AI Cam"], capture_output=True)
        subprocess.run(["nmcli", "connection", "up", ssid], capture_output=True)

    threading.Thread(target=_switch, daemon=True).start()
    return {
        "status": "ok",
        "message": f'Switching to "{ssid}". The Pi will leave the hotspot in ~2 seconds.',
        "find_at": f"{hostname}.local"
    }


@app.post("/enable-hotspot")
async def enable_hotspot():
    def _switch():
        import time
        time.sleep(2)
        subprocess.run(["nmcli", "connection", "modify", "Hailo AI Cam", "connection.autoconnect", "yes"], capture_output=True)
        subprocess.run(["nmcli", "connection", "up", "Hailo AI Cam"], capture_output=True)

    threading.Thread(target=_switch, daemon=True).start()
    return {"status": "ok", "message": "Switching to hotspot mode. Connect to the 'Hailo AI Cam' Wi-Fi network."}


@app.get("/{catchall:path}")
async def catch_all_route(catchall: str, request: Request):
    # Captive portals ping various URLs to check connectivity. 
    # Redirecting them to the root serves the captive portal landing page.
    return RedirectResponse(url="/")


if __name__ == "__main__":
    import uvicorn
    import threading
    import socketserver
    import http.server
    import os
    import subprocess

    def generate_self_signed_cert():
        if not os.path.exists("cert.pem") or not os.path.exists("key.pem"):
            print("Generating self-signed SSL certificate...")
            subprocess.run([
                "openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
                "-out", "cert.pem", "-keyout", "key.pem", "-days", "365",
                "-subj", "/CN=hailocam"
            ], check=True)

    # Generate the cert if missing
    generate_self_signed_cert()

    # Simple HTTP server on port 80 to serve the Captive Portal landing page without SSL warnings
    class RedirectHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            try:
                with open("index.html", "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            except Exception as e:
                self.send_response(500)
                self.end_headers()

    def run_http_redirect():
        try:
            with socketserver.TCPServer(("0.0.0.0", 80), RedirectHandler) as httpd:
                print("HTTP Captive Portal Server running on port 80...")
                httpd.serve_forever()
        except PermissionError:
            print("Permission denied: You must run this script with 'sudo' to bind to ports 80 and 443.")
            os._exit(1)

    threading.Thread(target=run_http_redirect, daemon=True).start()

    # Run the main FastAPI server on port 443 with SSL
    print("HTTPS FastAPI Server running on port 443...")
    uvicorn.run(app, host="0.0.0.0", port=443, ssl_keyfile="key.pem", ssl_certfile="cert.pem")
