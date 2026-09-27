# helmet_seatbelt_detect.py (final)
import os
import cv2
import time
import queue
import threading
import datetime
import requests
import numpy as np
import easyocr
import logging
from ultralytics import YOLO

# ----------------------------
# Logging
# ----------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ----------------------------
# Paths & config
# ----------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_DIR = os.path.join(BASE_DIR, "models")

VEHICLE_MODEL_PATH = os.path.join(MODEL_DIR, "yolov8n.pt")
HELMET_MODEL_PATH = os.path.join(MODEL_DIR, "helmet_detector.pt")
SEATBELT_MODEL_PATH = os.path.join(MODEL_DIR, "seatbelt_detector.pt")
PLATE_MODEL_PATH = os.path.join(MODEL_DIR, "number_plate_detector.pt")

# Django endpoints (local)
DJANGO_API_FIND = "http://127.0.0.1:8000/api/find_owner_by_plate/"
DJANGO_API_RECORD = "http://127.0.0.1:8000/api/record_violation/"

SAVE_PATH = os.path.join(BASE_DIR, "detection", "violations")
os.makedirs(SAVE_PATH, exist_ok=True)

MIN_CONF = 0.3
ALERT_COOLDOWN = 60  # seconds

# ----------------------------
# Load YOLOv8 models
# ----------------------------
logger.info("Loading YOLO models...")
vehicle_model = YOLO(VEHICLE_MODEL_PATH)
helmet_model = YOLO(HELMET_MODEL_PATH)
seatbelt_model = YOLO(SEATBELT_MODEL_PATH)
plate_model = YOLO(PLATE_MODEL_PATH)
logger.info("Models loaded.")

# ----------------------------
# EasyOCR
# ----------------------------
reader = easyocr.Reader(['en'], gpu=False)

# ----------------------------
# Alert queue (local to detection module)
# ----------------------------
alert_queue = queue.Queue()
recent_alerts = {}

def can_alert(plate_text):
    now = time.time()
    last = recent_alerts.get(plate_text, 0)
    if now - last > ALERT_COOLDOWN:
        recent_alerts[plate_text] = now
        return True
    return False

def send_alert_via_api(plate_text, violation_type, image_path=None):
    """
    Post to Django record_violation endpoint which will create DB record
    and send notifications (Email/SMS). This keeps alerts centralized in Django.
    """
    if plate_text and not can_alert(plate_text):
        logger.debug("Cooldown for %s", plate_text)
        return

    data = {"vehicle_number": plate_text, "violation_type": violation_type, "location": ""}
    files = {}
    try:
        if image_path and os.path.exists(image_path):
            files['image'] = open(image_path, 'rb')
        resp = requests.post(DJANGO_API_RECORD, data=data, files=files, timeout=5)
        logger.debug("record_violation POST status: %s", getattr(resp, 'status_code', None))
    except Exception as e:
        logger.exception("Failed to POST record_violation: %s", e)
    finally:
        if files:
            files['image'].close()

def alert_worker():
    while True:
        plate_text, violation_type, image_path = alert_queue.get()
        try:
            send_alert_via_api(plate_text, violation_type, image_path)
        except Exception:
            logger.exception("alert_worker failed")
        finally:
            alert_queue.task_done()

threading.Thread(target=alert_worker, daemon=True).start()

# ----------------------------
# Helpers: save, OCR, preprocess
# ----------------------------
def save_violation_image(frame, label):
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{label}_{ts}.jpg".replace(" ", "_")
    path = os.path.join(SAVE_PATH, filename)
    cv2.imwrite(path, frame)
    return path

def normalize_plate_text(s):
    if not s:
        return None
    out = "".join(filter(str.isalnum, s)).upper()
    return out if out else None

def ocr_on_image(img, min_len=4):
    try:
        results = reader.readtext(img, detail=1)  # bbox, text, conf
    except Exception as e:
        logger.exception("EasyOCR fail: %s", e)
        return []
    candidates = []
    for bbox, text, conf in results:
        if text:
            txt = normalize_plate_text(text)
            if txt and len(txt) >= min_len:
                candidates.append((txt, float(conf)))
    candidates.sort(key=lambda x: x[1], reverse=True)
    return candidates

def preprocess_for_ocr(crop):
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    filtered = cv2.bilateralFilter(gray, 9, 75, 75)
    thresh = cv2.adaptiveThreshold(filtered, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY, 11, 2)
    return thresh

def extract_plate_text(frame, boxes):
    candidates = []
    for box in boxes or []:
        try:
            coords = box.xyxy[0]
            x1, y1, x2, y2 = map(int, coords)
        except Exception:
            try:
                coords = list(box.xyxy)[0]
                x1, y1, x2, y2 = map(int, coords)
            except Exception:
                continue
        pad_x = int((x2 - x1) * 0.12) or 5
        pad_y = int((y2 - y1) * 0.18) or 5
        xa = max(0, x1 - pad_x); xb = min(frame.shape[1], x2 + pad_x)
        ya = max(0, y1 - pad_y); yb = min(frame.shape[0], y2 + pad_y)
        crop = frame[ya:yb, xa:xb]
        if crop.size == 0:
            continue

        cands = ocr_on_image(crop)
        if cands:
            candidates.extend(cands)
            # save debug crop of best candidate
            debug_path = os.path.join(SAVE_PATH, f"plate_{cands[0][0]}_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg")
            cv2.imwrite(debug_path, crop)

        prep = preprocess_for_ocr(crop)
        candidates.extend(ocr_on_image(prep))

    if not candidates:
        # fallback: whole frame
        candidates.extend(ocr_on_image(frame))
        candidates.extend(ocr_on_image(preprocess_for_ocr(frame)))

    if candidates:
        candidates = sorted(candidates, key=lambda x: x[1], reverse=True)
        best = candidates[0][0]
        logger.info("Plate OCR selected: %s (conf=%.2f)", best, candidates[0][1])
        return normalize_plate_text(best)
    return None

def inside_box(box, x1, y1, x2, y2):
    try:
        bx1, by1, bx2, by2 = map(int, box.xyxy[0])
    except Exception:
        try:
            coords = list(box.xyxy)[0]
            bx1, by1, bx2, by2 = map(int, coords)
        except Exception:
            return False
    return bx1 >= x1 - 5 and by1 >= y1 - 5 and bx2 <= x2 + 5 and by2 <= y2 + 5

def query_owner_api(plate_text):
    if not plate_text:
        return None
    try:
        resp = requests.get(DJANGO_API_FIND, params={"plate": plate_text}, timeout=4)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug("query_owner_api failed: %s", e)
    return None

# ----------------------------
# Main processing pipeline
# ----------------------------
def process_frame(frame):
    vehicle_results = vehicle_model(frame)
    processed = set()

    for vres in vehicle_results:
        for vbox in (vres.boxes or []):
            try:
                conf = float(vbox.conf[0])
            except Exception:
                try:
                    conf = float(vbox.conf)
                except Exception:
                    conf = 0.0
            if conf < MIN_CONF:
                continue

            try:
                cls_idx = int(vbox.cls[0])
            except Exception:
                cls_idx = int(vbox.cls)

            lbl = vehicle_model.names[cls_idx].lower()
            if lbl not in ("car", "truck", "bus", "motorcycle", "bicycle", "van"):
                continue

            try:
                x1, y1, x2, y2 = map(int, vbox.xyxy[0])
            except Exception:
                coords = list(vbox.xyxy)[0]
                x1, y1, x2, y2 = map(int, coords)

            cv2.rectangle(frame, (x1, y1), (x2, y2), (150,150,150), 2)
            cv2.putText(frame, f"{lbl} {conf:.2f}", (x1, y1-8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (150,150,150), 2)

            vehicle_id = (x1, y1, x2, y2)
            if vehicle_id in processed:
                continue
            processed.add(vehicle_id)

            vehicle_crop = frame[y1:y2, x1:x2] if (y2>y1 and x2>x1) else frame

            # Bike: helmet detection
            if lbl in ("motorcycle", "bicycle"):
                helmet_results = helmet_model(frame)
                for hr in helmet_results:
                    for box in (hr.boxes or []):
                        if not inside_box(box, x1, y1, x2, y2):
                            continue
                        try:
                            conf_h = float(box.conf[0])
                        except Exception:
                            conf_h = float(box.conf)
                        if conf_h < MIN_CONF:
                            continue
                        try:
                            h_label = helmet_model.names[int(box.cls[0])].lower()
                        except Exception:
                            h_label = helmet_model.names[int(box.cls)].lower()
                        if "no_helmet" in h_label or "without_helmet" in h_label or "nohelmet" in h_label:
                            bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0,0,255), 3)
                            cv2.putText(frame, f"{h_label} {conf_h:.2f}", (bx1, by1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
                            img_path = save_violation_image(frame, "no_helmet")

                            # plate detection (prefer inside vehicle box)
                            plate_results = plate_model(frame)
                            plate_boxes = [b for b in (plate_results[0].boxes or []) if inside_box(b, x1, y1, x2, y2)]
                            plate_text = extract_plate_text(frame, plate_boxes)
                            if not plate_text:
                                plate_text = extract_plate_text(vehicle_crop, [])
                            if not plate_text:
                                plate_text = extract_plate_text(frame, [])

                            owner = query_owner_api(plate_text)
                            # record & alert via Django
                            alert_plate = plate_text or "UNKNOWN"
                            alert_queue.put((alert_plate, "No Helmet", img_path))

            # Car/Truck/Van: seatbelt detection
            elif lbl in ("car", "truck", "van"):
                seat_results = seatbelt_model(vehicle_crop)
                for sr in seat_results:
                    for box in (sr.boxes or []):
                        try:
                            conf_s = float(box.conf[0])
                        except Exception:
                            conf_s = float(box.conf)
                        if conf_s < MIN_CONF:
                            continue
                        try:
                            s_label = seatbelt_model.names[int(box.cls[0])].lower()
                        except Exception:
                            s_label = seatbelt_model.names[int(box.cls)].lower()

                        # convert box coords to full-frame
                        try:
                            bx1, by1, bx2, by2 = map(int, box.xyxy[0])
                        except Exception:
                            coords = list(box.xyxy)[0]
                            bx1, by1, bx2, by2 = map(int, coords)
                        bx1 += x1; bx2 += x1; by1 += y1; by2 += y1

                        if "without_seatbelt" in s_label or "no_seatbelt" in s_label or "noseatbelt" in s_label:
                            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0,0,255), 3)
                            cv2.putText(frame, f"{s_label} {conf_s:.2f}", (bx1, by1-10), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2)
                            img_path = save_violation_image(frame, "no_seatbelt")

                            # plate detection inside vehicle crop first
                            plate_results = plate_model(vehicle_crop)
                            plate_boxes = plate_results[0].boxes if plate_results and plate_results[0].boxes else []
                            plate_text = extract_plate_text(vehicle_crop, plate_boxes)
                            if not plate_text:
                                plate_text = extract_plate_text(frame, [])
                            owner = query_owner_api(plate_text)
                            alert_plate = plate_text or "UNKNOWN"
                            alert_queue.put((alert_plate, "No Seatbelt", img_path))
                        else:
                            cv2.rectangle(frame, (bx1, by1), (bx2, by2), (0,255,0), 2)

    return frame


# Frame generator used by Django streaming view
def gen_frames(source=0):
    cap = cv2.VideoCapture(source)
    if not cap.isOpened():
        logger.error("Cannot open source: %s", source)
        return
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame = process_frame(frame)
        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
    cap.release()
