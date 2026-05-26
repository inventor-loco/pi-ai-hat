import sys
import numpy as np
import cv2
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

from hailo_platform import VDevice, HEF, InferVStreams, InputVStreamParams, OutputVStreamParams, FormatType

TARGET_MODEL = "yolov8n.hef"
hef = HEF(TARGET_MODEL)

print("Initializing Hailo physical hardware device...")
target_device = VDevice()
network_group = target_device.configure(hef)[0]

class HailoInferenceHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        raw_img_bytes = self.rfile.read(content_length)
        
        nparr = np.frombuffer(raw_img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        input_vstream_infos = hef.get_input_vstream_infos()
        shape_tuple = input_vstream_infos[0].shape
        
        if len(shape_tuple) == 4:
            height, width = shape_tuple[1], shape_tuple[2]
        else:
            height, width = shape_tuple[0], shape_tuple[1]
            
        resized_img = cv2.resize(img, (width, height))
        input_data = {input_vstream_infos[0].name: np.expand_dims(resized_img, axis=0)}
        
        input_vstreams_params = InputVStreamParams.make(network_group, format_type=FormatType.UINT8)
        output_vstreams_params = OutputVStreamParams.make(network_group, format_type=FormatType.FLOAT32)
        
        # Trigger Inference
        with InferVStreams(network_group, input_vstreams_params, output_vstreams_params) as vstreams:
            with network_group.activate():
                infer_results = vstreams.infer(input_data)
        
        # Parse the NMS arrays natively
        output_layer_name = list(infer_results.keys())[0]
        raw_output = infer_results[output_layer_name]
        real_detections = []
        
        try:
            batch_data = raw_output[0]
            for class_id, class_boxes in enumerate(batch_data):
                for box in class_boxes:
                    confidence = float(box[4])
                    if confidence > 0.4:
                        real_detections.append({
                            "class": f"Class {class_id}",
                            "confidence": round(confidence, 2),
                            "box": [
                                int(box[1] * width),  
                                int(box[0] * height), 
                                int(box[3] * width),  
                                int(box[2] * height)  
                            ]
                        })
        except Exception as e:
            print(f"Error parsing NMS tensors: {e}")

        if not real_detections:
            real_detections = [{"class": "Nothing Detected", "confidence": 1.0, "box": [10, 10, 20, 20]}]

        response_data = {
            "status": "success",
            "detections": real_detections
        }
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response_data).encode('utf-8'))

def run_daemon():
    server_address = ('127.0.0.1', 8001)
    httpd = HTTPServer(server_address, HailoInferenceHandler)
    print("Hailo Core Daemon listening locally on port 8001...")
    try:
        httpd.serve_forever()
    finally:
        print("\nReleasing Hailo hardware device control...")
        target_device.release()

if __name__ == '__main__':
    run_daemon()
