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

This is especially important for:
- object-detection weights,
- license-plate detection weights,
- OCR weights,
- face models.

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

# 3. CURRENT BASELINE

| Component | Purpose | Code/Project License | Exact Weight/Artifact Status | Shipment Status |
|---|---|---|---|---|
| YOLOX | Person/vehicle detection | Apache-2.0 | Exact checkpoint must be recorded | REVIEW REQUIRED |
| OpenCV 4.5+ | Video/CV | Apache-2.0 | Library, no model weight | VERIFIED |
| YuNet model from OpenCV Zoo | Face detection | Model directory MIT | Exact file/checksum should be recorded | REVIEW REQUIRED |
| RapidOCR | OCR engine | Apache-2.0 | Underlying model artifacts must be recorded | REVIEW REQUIRED |
| ONNX Runtime | Local inference runtime | MIT | No model weight | VERIFIED |
| Dedicated plate detector | ANPR plate localization | Depends on exact model | Not selected yet | BLOCKED |
| FastAPI | Backend API | Permissive/open-source | No model | REVIEWED |
| React | Frontend | MIT | No model | REVIEWED |
| Vite | Frontend build | MIT | No model | REVIEWED |
| SQLAlchemy | Database abstraction | MIT | No model | REVIEWED |
| Alembic | DB migrations | MIT | No model | REVIEWED |
| SQLite | MVP database | Public domain | No model | REVIEWED |

---

# 4. OBJECT DETECTION — YOLOX

## Project

**YOLOX**

Official project:

```text
https://github.com/Megvii-BaseDetection/YOLOX
```

The official repository states that YOLOX is licensed under **Apache-2.0**. citeturn895516search2

## Purpose

- person detection
- vehicle detection
- vehicle classification

## Current decision

Use YOLOX as the detector baseline instead of Ultralytics YOLO.

## Important checkpoint rule

The project must not assume:

```text
YOLOX repository Apache-2.0
=
every downloaded YOLOX checkpoint automatically cleared
```

Before final shipment, record the exact checkpoint:

```text
model_name:
model_variant:
source:
release/tag:
filename:
SHA256:
weight_license:
attribution:
commercial_use_status:
```

## Current status

```text
Code/project: VERIFIED
Exact checkpoint: REVIEW REQUIRED
```

---

# 5. FACE DETECTION — OPENCV YUNET

## Project

OpenCV Zoo — YuNet face detection.

The OpenCV Zoo repository includes YuNet face detection and states that individual model directories have their own licensing information. citeturn895516search0turn895516search1

The YuNet model directory currently includes an MIT license. citeturn895516search8

## Purpose

Detect visible faces.

## Current decision

Use YuNet for MVP face detection.

## Artifact to record

Example:

```text
face_detection_yunet_2023mar_int8bq.onnx
```

The exact selected file must be recorded with:

```text
source URL
exact filename
SHA256
license
```

## Current status

```text
Project/model directory license: VERIFIED
Exact shipped artifact: REVIEW REQUIRED
```

---

# 6. ANPR — PLATE DETECTOR

## Current status

```text
NOT SELECTED
```

The plate detector must be selected deliberately.

OpenCV Zoo currently includes **LPD_YuNet** as a license-plate detection example/model, but the model-specific license and exact artifact must be checked before it is adopted. OpenCV Zoo itself states that individual models have their own licensing considerations. citeturn895516search0turn895516search1

## Selection rule

The chosen plate detector must have:

- identifiable source,
- identifiable exact checkpoint,
- documented license,
- usable redistribution/commercial terms for the intended project,
- reproducible download/source,
- checksum.

If the license is unclear:

```text
DO NOT SHIP
```

---

# 7. OCR — RAPIDOCR

## Project

**RapidOCR**

Official project:

```text
https://github.com/RapidAI/RapidOCR
```

RapidOCR states that its engineering/source code is Apache-2.0 licensed. It also explains that the OCR model weights originate from upstream PaddleOCR models and that exact model provenance/license information needs to be considered. citeturn640997search1turn640997search6

## Purpose

- read detected license plates
- perform OCR after plate cropping

## Current decision

Use:

```text
RapidOCR
+
ONNX Runtime
```

## Model rule

Record the exact OCR model artifact used by the project.

Required:

```text
model name
upstream source
exact artifact
conversion status
SHA256
upstream license
attribution
commercial-use status
```

## Current status

```text
RapidOCR source: VERIFIED
Exact OCR model artifact: REVIEW REQUIRED
```

---

# 8. ONNX RUNTIME

## Project

Microsoft ONNX Runtime.

The official repository states that ONNX Runtime is licensed under the **MIT License**. citeturn640997search0turn640997search3

## Purpose

- local model inference runtime
- OCR inference
- other ONNX model execution where selected

## Status

```text
VERIFIED
```

Remember that a permissive runtime does not automatically make the model executed by that runtime permissively licensed.

---

# 9. OPENCV

OpenCV states that:

- OpenCV 4.5.0 and higher use Apache-2.0,
- OpenCV 4.4.0 and lower use the 3-clause BSD license. citeturn640997search2

## IBVAP decision

Use:

```text
OpenCV >= 4.5.0
```

and pin the exact tested version in the final dependency lock.

## Status

```text
VERIFIED
```

---

# 10. FRONTEND / API / DATABASE DEPENDENCIES

The final repository should generate a complete dependency inventory from the actual installed environment.

At minimum include:

```text
package
version
license
source
```

Required ecosystem includes:

```text
FastAPI
Uvicorn
Pydantic
React
TypeScript
Vite
SQLAlchemy
Alembic
OpenCV
YOLOX
ByteTrack implementation
RapidOCR
ONNX Runtime
```

Do not assume a package's license without checking the exact package distribution used by the final build.

---

# 11. THIRD-PARTY LICENSE NOTICE

The final application should contain a notice file such as:

```text
THIRD_PARTY_NOTICES.md
```

It should identify the third-party software included in the distribution and preserve required notices/attribution.

At minimum, record:

```text
Component
Version
License
Copyright/Attribution
Source
```

---

# 12. MODEL MANIFEST FORMAT

For every model used by IBVAP, create an entry like:

```yaml
model_name:
purpose:
framework:
source_url:
release:
filename:
sha256:
code_license:
weights_license:
training_data:
commercial_use_status:
redistribution_status:
attribution_required:
notes:
status:
```

Example:

```yaml
model_name: YuNet
purpose: face_detection
framework: OpenCV DNN
source_url: <official-source>
release: <exact-release>
filename: <exact-file>
sha256: <sha256>
code_license: MIT
weights_license: MIT
training_data: unknown/not stated
commercial_use_status: review_required
redistribution_status: review_required
attribution_required: preserve_MIT_notice
notes:
status: REVIEW_REQUIRED
```

Do not invent missing fields.

Use:

```text
UNKNOWN
```

when authoritative information is not available.

---

# 13. CHECKSUM POLICY

Every shipped model file must have:

```text
SHA256
```

recorded.

Purpose:

- reproducibility
- corruption detection
- preventing accidental model replacement
- verifying the exact tested artifact

Example:

```text
sha256: <64-character SHA-256 hash>
```

---

# 14. MODEL DOWNLOAD POLICY

During development, models may be downloaded using documented setup steps.

For the final demo environment:

```text
MODEL FILE
   ↓
PINNED VERSION
   ↓
CHECKSUM VERIFIED
   ↓
LICENSE RECORDED
   ↓
LOCAL MODEL STORAGE
```

Do not make final startup depend on an undocumented internet download.

---

# 15. NO AUTOMATIC MODEL REPLACEMENT

Antigravity must not automatically replace a model with:

- another checkpoint,
- a newer release,
- a different vendor,
- a different license,

without updating:

```text
MODEL_LICENSES.md
MODEL MANIFEST
ARCHITECTURE.md
```

and rerunning the affected tests.

---

# 16. LICENSE DECISION FOR YOLO11

Ultralytics YOLO11 is intentionally **not** part of the IBVAP baseline.

Reason:

Ultralytics documents YOLO11 under AGPL-3.0 and Enterprise licensing. The project therefore chose YOLOX as the baseline detector to reduce licensing complexity for the MVP.

This decision should remain locked unless the project intentionally chooses a different licensing strategy.

---

# 17. PLATE MODEL SELECTION GATE

Before ANPR implementation is considered final:

```text
[ ] Plate model selected
[ ] Official source recorded
[ ] Exact weight file recorded
[ ] SHA256 recorded
[ ] Weight license verified
[ ] Code license verified
[ ] Redistribution status understood
[ ] Commercial-use status understood
[ ] Attribution requirements recorded
[ ] License notice added
```

If any critical item is unknown:

```text
STATUS = BLOCKED
```

---

# 18. FINAL PRE-SHIP LICENSE AUDIT

Before public release, submission containing the software, or commercial use:

```text
[ ] All dependency versions pinned
[ ] All dependency licenses inventoried
[ ] YOLOX checkpoint verified
[ ] YuNet checkpoint verified
[ ] Plate detector verified
[ ] OCR model verified
[ ] ONNX Runtime recorded
[ ] OpenCV version verified
[ ] Third-party notices generated
[ ] Model SHA256 values recorded
[ ] Unknown licenses resolved
```

---

# 19. IMPORTANT LEGAL DISCLAIMER

This document is an **engineering license/provenance register, not legal advice**.

For the SIH prototype, this document provides traceability and prevents accidental use of clearly unsuitable artifacts.

Before commercial distribution, private closed-source deployment, or a material public release, have the final dependency/model set reviewed by an appropriate legal/licensing professional if needed.

---

# 20. CURRENT REGISTER STATE

```text
Overall status: YELLOW

Reason:
The permissive baseline has been selected, but the exact
pretrained model/checkpoint artifacts—especially the dedicated
ANPR plate detector and OCR weights—must be recorded and verified
before the project is treated as fully license-cleared.
```

---

# 21. FINAL RULE

The project may say:

> “The IBVAP architecture is designed around permissively licensed/open-source components.”

It should NOT say:

> “Every model is automatically 100% commercially cleared.”

That stronger statement is allowed only after the exact model artifacts and their applicable licenses have been verified.
