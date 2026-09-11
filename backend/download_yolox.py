import urllib.request
import hashlib
from pathlib import Path

def download_model():
    out_dir = Path(__file__).resolve().parent.parent / "models" / "detection"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "yolox_tiny.onnx"

    url = "https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx"
    print(f"Downloading YOLOX model from {url}...")
    
    # User-agent header to avoid any GitHub throttling
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req) as response, open(out_file, "wb") as out:
        out.write(response.read())

    hasher = hashlib.sha256()
    with open(out_file, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            hasher.update(chunk)
    sha256 = hasher.hexdigest()

    print(f"Downloaded {out_file.name} successfully!")
    print(f"Size: {out_file.stat().st_size} bytes")
    print(f"SHA256: {sha256}")

if __name__ == "__main__":
    download_model()
