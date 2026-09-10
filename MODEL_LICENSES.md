# IBVAP — MODEL & DEPENDENCY LICENSE REGISTER

**Project:** IBVAP — Intelligent Border Video Analytics Platform  
**SIH:** SIH26187  
**Document Status:** MVP License/Provenance Register  
**Purpose:** Track the exact code libraries, model artifacts and licenses used by IBVAP so that the final prototype does not silently include an incompatible or unknown model/checkpoint.

---

# 1. IMPORTANT PRINCIPLE

A software repository's license and a pretrained model/checkpoint's license are not automatically the same thing.

Therefore, IBVAP tracks:

```text
Code License
+
Model/Weight License
+
Model Provenance
+
Training/Data Terms where discoverable
+
Attribution Requirements
```

A component is not considered **cleared for shipment** until the exact artifact being distributed has been identified and its licensing status reviewed.

---

# 2. STATUS DEFINITIONS

```text
VERIFIED
```
Exact artifact and relevant license information have been checked from an authoritative source.

```text
REVIEW REQUIRED
```
Code license is known, but the exact model/checkpoint or another important term has not yet been independently verified.

```text
BLOCKED
```
The artifact must not be shipped until the licensing issue is resolved.

```text
REJECTED
```
Artifact will not be used in the project.

---

# 3. CURRENT BASELINE & MODEL REGISTER

| Component | Purpose | Code/Project License | Exact Weight/Artifact Status | Shipment Status |
|---|---|---|---|---|
| **YOLOX (Tiny ONNX)** | Person/vehicle detection | Apache-2.0 | `yolox_tiny.onnx` (SHA256: `427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7`) | **VERIFIED** |
| **YuNet (OpenCV Zoo)** | Face detection | MIT | `face_detection_yunet_2023mar.onnx` (SHA256: `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4`) | **VERIFIED** |
| **PP-OCRv4 DBNet (RapidOCR)** | Plate / text candidate detector | Apache-2.0 | `ch_PP-OCRv4_det_infer.onnx` (SHA256: `d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9`) | **VERIFIED** |
| **PP-OCRv4 Recognizer (RapidOCR)** | License plate character OCR | Apache-2.0 | `ch_PP-OCRv4_rec_infer.onnx` (SHA256: `48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b`) | **VERIFIED** |
| **PP-OCR Text Cls (RapidOCR)** | Text orientation classifier | Apache-2.0 | `ch_ppocr_mobile_v2.0_cls_infer.onnx` (SHA256: `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c`) | **VERIFIED** |
| OpenCV 4.5+ | Video/CV & Face Detector | Apache-2.0 | Library, native DNN backend | **VERIFIED** |
| ByteTrack | Multi-object tracking | MIT | Pure Python + SciPy algorithm | **VERIFIED** |
| ONNX Runtime | Local inference runtime | MIT | Engine runtime | **VERIFIED** |
| FastAPI | Backend API | MIT | Library | **VERIFIED** |
| React | Frontend | MIT | Framework | **VERIFIED** |
| Vite | Frontend build | MIT | Build tool | **VERIFIED** |
| SQLAlchemy 2.x | Database abstraction | MIT | Library | **VERIFIED** |
| Alembic | DB migrations | MIT | Library | **VERIFIED** |
| SQLite | MVP database | Public domain | Engine | **VERIFIED** |

---

# 4. OBJECT DETECTION — YOLOX MANIFEST

```yaml
model_name: YOLOX
model_variant: yolox_tiny
framework: ONNX Runtime
source_url: https://github.com/Megvii-BaseDetection/YOLOX/releases/download/0.1.1rc0/yolox_tiny.onnx
release_tag: 0.1.1rc0
filename: yolox_tiny.onnx
input_resolution: 416x416
size_bytes: 20219662
sha256: 427cc366d34e27ff7a03e2899b5e3671425c262ea2291f88bb942bc1cc70b0f7
code_license: Apache-2.0
weights_license: Apache-2.0
commercial_use_status: Permitted (Apache-2.0)
attribution_required: Preserve Megvii YOLOX Apache-2.0 notice
status: VERIFIED
```

---

# 5. FACE DETECTION — OPENCV YUNET MANIFEST

```yaml
model_name: YuNet
model_variant: face_detection_yunet_2023mar
framework: OpenCV DNN (FaceDetectorYN)
source_url: https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx
release_tag: 2023mar
filename: face_detection_yunet_2023mar.onnx
input_resolution: Dynamic / 320x320 - 1280x720
size_bytes: 232589
sha256: 8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4
code_license: MIT
weights_license: MIT
commercial_use_status: Permitted (MIT License)
attribution_required: Preserve OpenCV Zoo YuNet MIT notice
status: VERIFIED
```

---

# 6. ANPR / OCR — RAPIDOCR PP-OCRV4 MANIFEST

```yaml
model_name: PP-OCRv4
model_variant: ch_PP-OCRv4 (det + rec + cls)
framework: ONNX Runtime (via rapidocr-onnxruntime 1.4.4)
source_url: https://github.com/RapidAI/RapidOCR / https://github.com/PaddlePaddle/PaddleOCR
release_tag: v1.4.4
detection_model:
  filename: ch_PP-OCRv4_det_infer.onnx
  size_bytes: 4745517
  sha256: d2a7720d45a54257208b1e13e36a8479894cb74155a5efe29462512d42f49da9
recognition_model:
  filename: ch_PP-OCRv4_rec_infer.onnx
  size_bytes: 10857958
  sha256: 48fc40f24f6d2a207a2b1091d3437eb3cc3eb6b676dc3ef9c37384005483683b
classifier_model:
  filename: ch_ppocr_mobile_v2.0_cls_infer.onnx
  size_bytes: 585532
  sha256: e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c
code_license: Apache-2.0
weights_license: Apache-2.0
commercial_use_status: Permitted (Apache-2.0)
attribution_required: Preserve RapidAI and PaddleOCR Apache-2.0 notices
status: VERIFIED
```

---

# 7. REGISTER AUDIT STATE

```text
Phase 2 Status: GREEN (YOLOX Object Detector VERIFIED)
Phase 3 Status: GREEN (ByteTrack Multi-Object Tracking VERIFIED)
Phase 4 Status: GREEN (YuNet Face Detector Checkpoint VERIFIED)
Phase 5 Status: GREEN (RapidOCR PP-OCRv4 ANPR Engine VERIFIED)
Ultralytics YOLO Exclusion: VERIFIED (Zero Ultralytics dependencies)
```
