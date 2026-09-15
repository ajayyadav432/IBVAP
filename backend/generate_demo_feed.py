import cv2
import numpy as np
from pathlib import Path

def generate_sample_video():
    out_dir = Path(__file__).resolve().parent.parent / "data" / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "sample_feed.mp4"

    width, height, fps = 640, 360, 25
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))

    for i in range(150):
        frame = np.zeros((height, width, 3), dtype=np.uint8)
        # Dark control room backdrop
        frame[:] = (18, 18, 18)
        
        # Grid lines
        for x in range(0, width, 40):
            cv2.line(frame, (x, 0), (x, height), (30, 30, 30), 1)
        for y in range(0, height, 40):
            cv2.line(frame, (0, y), (width, y), (30, 30, 30), 1)
        
        # Simulated moving target
        cx = int((i * 4) % (width - 60)) + 30
        cy = int(height / 2 + np.sin(i / 10.0) * 40)
        cv2.rectangle(frame, (cx - 15, cy - 30), (cx + 15, cy + 30), (60, 60, 200), -1)
        cv2.circle(frame, (cx, cy - 35), 8, (70, 70, 220), -1)

        # Simulated perimeter wire
        cv2.line(frame, (20, height - 60), (width - 20, height - 60), (0, 0, 180), 2)
        cv2.putText(frame, "RESTRICTED PERIMETER ZONE", (25, height - 40), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 220), 1)

        # Simulated OSD overlay
        cv2.putText(frame, f"CAM 01: BOP-03 NORTH GATE [DEMO] - FRAME {i:04d}", (15, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 220, 220), 1)
        cv2.putText(frame, "REC 25 FPS 640x360", (15, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (0, 200, 0), 1)
        
        writer.write(frame)

    writer.release()
    print("Created test video successfully at:", out_path)

if __name__ == "__main__":
    generate_sample_video()
