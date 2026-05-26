from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
import httpx

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
    # Serves the frontend UI directly to anyone who visits the Pi's IP address
    return FileResponse("index.html")

@app.post("/process-frame")
async def process_frame(file: UploadFile = File(...)):
    img_bytes = await file.read()
    async with httpx.AsyncClient() as client:
        try:
            daemon_response = await client.post(
                "http://127.0.0.1:8001/",
                content=img_bytes,
                timeout=5.0
            )
            if daemon_response.status_code != 200:
                return {"status": "error", "message": f"Daemon Error: {daemon_response.status_code}"}
            return daemon_response.json()
        except httpx.ConnectError:
            return {"status": "error", "message": "Hailo daemon offline on port 8001."}
        except Exception as e:
            return {"status": "error", "message": f"Proxy crash: {str(e)}"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
