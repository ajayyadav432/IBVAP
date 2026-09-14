import cv2
from pathlib import Path
from app.services.inference.detector import YOLOXDetector

def inspect_video_vehicles():
    detector = YOLOXDetector()
    video_path = Path(__file__).resolve().parent.parent / "data" / "demo" / "sample_cctv.mp4"
    cap = cv2.VideoCapture(str(video_path))
    vehicle_count = 0
    frame_idx = 0
    max_frames = 500
    while cap.isOpened() and frame_idx < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % 25 == 0:
            dets = detector.detect(frame, conf_threshold=0.35)
            vehicles = [d for d in dets if d.class_name in ["car", "bus", "truck", "motorcycle"]]
            if vehicles:
                vehicle_count += len(vehicles)
                print(f"Frame {frame_idx:04d}: Found {len(vehicles)} vehicle(s)")
                for v in vehicles:
                    w = v.bbox[2] - v.bbox[0]
                    h = v.bbox[3] - v.bbox[1]
                    print(f"   [{v.class_name}] conf={v.confidence:.2f} bbox={v.bbox} (size={w}x{h})")
        frame_idx += 1
    cap.release()
    print(f"\nTotal vehicle detections sampled: {vehicle_count}")

if __name__ == "__main__":
    inspect_video_vehicles()
