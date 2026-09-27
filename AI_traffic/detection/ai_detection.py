# ai_detection.py
import cv2
import os
import datetime
import requests
import time
import numpy as np
from ultralytics import YOLO

# Optional OCR
try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"  # windows default path; adjust if needed
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False
    print("[WARN] pytesseract not available. OCR disabled.")

# Configuration - adjust paths / URLs
MODEL_PATHS = ["helmet_seatbelt.pt", "yolov8n.pt"]  # preferred: custom weights first
DJANGO_FIND_OWNER_API = "http://127.0.0.1:8000/api/find_owner_by_plate/"    # GET ?plate=...
DJANGO_RECORD_API = "http://127.0.0.1:8000/api/record_violation/"            # POST, multipart
CAMERA_INDEX = 0  # change to 1,2 if default webcam not available
CONF_THRESHOLD = 0.45  # detection confidence threshold

# Try to load the first available model in MODEL_PATHS
model = None
for p in MODEL_PATHS:
    if os.path.exists(p):
        print(f"[INFO] Loading model: {p}")
        model = YOLO(p)
        break

if model is None:
    # fallback: try to load standard yolov8n which ultralytics will download if not present
    print("[INFO] No custom model file found locally. Loading 'yolov8n.pt' via ultralytics (may be downloaded).")
    model = YOLO("yolov8n.pt")

# Helper: OCR cleanup
def ocr_plate_text(crop):
    if not OCR_AVAILABLE:
        return None
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    # Basic preprocessing - tune as required
    gray = cv2.bilateralFilter(gray, 9, 75, 75)
    _, thr = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    text = pytesseract.image_to_string(thr, config='--psm 7')  # single line mode
    text = ''.join(ch for ch in text if ch.isalnum())
    return text.upper() if text else None

# Utility: try multiple camera indices
def open_camera(indexes=(0,1,2)):
    for idx in indexes:
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)  # CAP_DSHOW often works better on Windows
        if cap is None or not cap.isOpened():
            print(f"[WARN] Camera index {idx} failed to open.")
            continue
        # try to read one frame
        ret, _ = cap.read()
        if ret:
            print(f"[INFO] Using camera index {idx}")
            return cap
        else:
            cap.release()
    return None

cap = open_camera((CAMERA_INDEX, 0, 1, 2))
if cap is None:
    raise SystemExit("[ERROR] Unable to open any camera. Close other apps using camera or change CAMERA_INDEX.")

os.makedirs("evidence", exist_ok=True)

def post_violation_to_server(violation_info, image_path):
    """
    violation_info: dict with keys: vehicle_number (may be None), violation_type, location
    image_path: path to saved evidence image
    """
    files = {'image': open(image_path, 'rb')}
    data = {
        'vehicle_number': violation_info.get('vehicle_number') or '',
        'violation_type': violation_info['violation_type'],
        'location': violation_info.get('location', 'Unknown Camera'),
    }
    try:
        resp = requests.post(DJANGO_RECORD_API, files=files, data=data, timeout=10)
        print("[INFO] Server response:", resp.status_code, resp.text)
    except Exception as e:
        print("[ERROR] Failed to post to server:", e)

def find_owner_by_plate(plate_text):
    if not plate_text:
        return None
    try:
        resp = requests.get(DJANGO_FIND_OWNER_API, params={'plate': plate_text}, timeout=8)
        if resp.status_code == 200:
            return resp.json()  # expected to return JSON with owner info or {'found': False}
        else:
            print("[WARN] find_owner API status:", resp.status_code, resp.text)
    except Exception as e:
        print("[ERROR] find_owner_by_plate request failed:", e)
    return None

# Start detection loop
last_sent_time = 0
MIN_COOLDOWN = 8  # seconds between sending consecutive events for same frame (avoid duplicates)

print("[INFO] Starting detection loop. Press 'q' to quit.")
while True:
    ret, frame = cap.read()
    if not ret:
        print("[WARN] Frame not grabbed. Retrying...")
        time.sleep(0.2)
        continue

    # Run YOLO inference (fast)
    results = model(frame, stream=False)  # returns BatchPredictResult object
    # results[0].boxes contains detected boxes
    boxes = results[0].boxes if len(results) > 0 else []
    # boxes.data format: [x1, y1, x2, y2, conf, cls]
    if hasattr(boxes, 'data') and len(boxes.data):
        for row in boxes.data.tolist():
            x1, y1, x2, y2, conf, cls = row
            conf = float(conf)
            cls = int(cls)
            label = model.names[cls] if hasattr(model, 'names') else str(cls)
            if conf < CONF_THRESHOLD:
                continue

            # For debugging show all detected classes
            color = (0,255,0)
            text = f"{label} {conf:.2f}"

            # If your custom model contains no_helmet or no_seatbelt classes:
            if label.lower() in ['no_helmet', 'no_seatbelt']:
                color = (0,0,255)
                text = f"VIOLATION: {label}"

                # Save evidence
                ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                fname = os.path.join("evidence", f"violation_{label}_{ts}.jpg")
                cv2.imwrite(fname, frame)
                print("[INFO] Violation detected:", label, "saving", fname)

                # try to find license plate among detections (if model detects license_plate)
                plate_text = None
                # search for a detected license_plate box
                if hasattr(boxes, 'data'):
                    for r2 in boxes.data.tolist():
                        _, _, _, _, conf2, cls2 = r2
                        lbl2 = model.names[int(cls2)]
                        if lbl2.lower() in ['license_plate', 'number_plate', 'plate']:
                            x1p, y1p, x2p, y2p = map(int, r2[:4])
                            plate_crop = frame[y1p:y2p, x1p:x2p]
                            plate_text = ocr_plate_text(plate_crop)
                            if plate_text:
                                print("[INFO] OCR extracted plate:", plate_text)
                                break

                # As fallback, try to run OCR on ROI near detected person/vehicle bottom area (best-effort)
                if plate_text is None and OCR_AVAILABLE:
                    # attempt to guess ROI within frame - heuristic, may need tuning
                    h, w = frame.shape[:2]
                    roi = frame[int(h*0.6):h, int(w*0.2):int(w*0.8)]
                    plate_text = ocr_plate_text(roi)
                    if plate_text:
                        print("[INFO] Fallback OCR plate text:", plate_text)

                owner_json = find_owner_by_plate(plate_text) if plate_text else None
                owner_plate = owner_json.get('vehicle_number') if owner_json and owner_json.get('found') else (plate_text or '')

                violation_info = {
                    'vehicle_number': owner_plate,
                    'violation_type': label,
                    'location': 'Camera-1'
                }

                # Throttle duplicate posts
                now = time.time()
                if now - last_sent_time > MIN_COOLDOWN:
                    post_violation_to_server(violation_info, fname)
                    last_sent_time = now
                else:
                    print("[DEBUG] Skipping duplicate send (cooldown).")

            # Draw box on frame for visualization
            x1i, y1i, x2i, y2i = map(int, [x1, y1, x2, y2])
            cv2.rectangle(frame, (x1i, y1i), (x2i, y2i), color, 2)
            cv2.putText(frame, text, (x1i, max(20, y1i-10)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

    # show frame
    cv2.imshow("AI Traffic Detection", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
