import cv2
import os
import sys
from pathlib import Path
import numpy as np
from rapidocr_onnxruntime import RapidOCR
from app.services.inference.detector import YOLOXDetector

# Force utf-8 stdout
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

def analyze_toll_cctv():
    video_path = Path(__file__).resolve().parent.parent / "data" / "demo" / "toll_cctv.mp4"
    if not video_path.exists():
        print(f"Error: Video file not found at {video_path}")
        return

    cap = cv2.VideoCapture(str(video_path))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = float(cap.get(cv2.CAP_PROP_FPS))
    frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration = frames / fps if fps > 0 else 0
    fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
    fourcc_str = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)])

    print("=" * 60)
    print("ANPR VIDEO ANALYSIS REPORT: DATA/DEMO/TOLL_CCTV.MP4")
    print("=" * 60)
    print(f"Resolution: {w}x{h}")
    print(f"FPS: {fps:.2f}")
    print(f"Total Frames: {frames}")
    print(f"Duration: {duration:.2f} seconds")
    print(f"Codec/FourCC: {fourcc_str} (H.264 / AVC)")
    print("-" * 60)

    detector = YOLOXDetector()
    ocr = RapidOCR()

    out_dir = Path(__file__).resolve().parent.parent / "data" / "demo" / "toll_analysis"
    out_dir.mkdir(parents=True, exist_ok=True)

    frame_idx = 0
    vehicle_records = []
    ocr_readings = []

    # Sample every 10 frames
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / fps
        if frame_idx % 10 == 0:
            dets = detector.detect(frame, conf_threshold=0.35)
            vehicles = [d for d in dets if d.class_name in ["car", "bus", "truck", "motorcycle"]]
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            sharpness = cv2.Laplacian(gray, cv2.CV_64F).var()
            brightness = np.mean(gray)

            for v in vehicles:
                bx1, by1, bx2, by2 = v.bbox
                vw = bx2 - bx1
                vh = by2 - by1
                if vw > 80 and vh > 60:
                    crop = frame[by1:by2, bx1:bx2]
                    res, elapse = ocr(crop)
                    if res:
                        for r in res:
                            txt = r[1]
                            score = r[2]
                            ocr_readings.append({
                                "frame_idx": frame_idx,
                                "timestamp": timestamp,
                                "vehicle_type": v.class_name,
                                "bbox": v.bbox,
                                "text": txt,
                                "score": score,
                                "sharpness": sharpness,
                            })
                            print(f"[Frame {frame_idx:03d} | {timestamp:.2f}s] Vehicle {v.class_name} ({vw}x{vh}px) -> OCR Text: '{txt}' (conf: {score:.2f})")
            
            if vehicles:
                vehicle_records.append({
                    "frame_idx": frame_idx,
                    "timestamp": timestamp,
                    "count": len(vehicles),
                    "vehicles": vehicles,
                    "sharpness": sharpness,
                    "brightness": brightness,
                })

        frame_idx += 1

    cap.release()

    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"Total sampled frames: {frame_idx // 10}")
    print(f"Frames containing vehicles: {len(vehicle_records)}")
    print(f"OCR readings captured: {len(ocr_readings)}")

    # Distinct license plate reads
    plates = {}
    for r in ocr_readings:
        t = r["text"].strip().upper()
        if len(t) >= 4:
            if t not in plates or r["score"] > plates[t]["score"]:
                plates[t] = r

    print("\nDistinct Candidate Readings:")
    for k, v in sorted(plates.items(), key=lambda x: x[1]["score"], reverse=True):
        print(f"  Plate candidate: '{k}' (conf: {v['score']:.2f}) at Frame {v['frame_idx']} ({v['timestamp']:.2f}s, {v['vehicle_type']})")

if __name__ == "__main__":
    analyze_toll_cctv()
