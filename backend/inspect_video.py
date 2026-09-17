import cv2
from pathlib import Path

def inspect():
    path = Path(__file__).resolve().parent.parent / "data" / "demo" / "sample_cctv.mp4"
    if not path.exists():
        print(f"File not found: {path}")
        return
    cap = cv2.VideoCapture(str(path))
    if cap.isOpened():
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS))
        frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = frames / fps if fps > 0 else 0
        fourcc_int = int(cap.get(cv2.CAP_PROP_FOURCC))
        fourcc_str = "".join([chr((fourcc_int >> 8 * i) & 0xFF) for i in range(4)])
        print(f"Resolution: {w}x{h}")
        print(f"FPS: {fps:.2f}")
        print(f"Frames: {frames}")
        print(f"Duration: {duration:.2f}s")
        print(f"Codec/FourCC: {fourcc_str} (avc1/H.264 MP4)")
        cap.release()
    else:
        print("Could not open video file.")

if __name__ == "__main__":
    inspect()
