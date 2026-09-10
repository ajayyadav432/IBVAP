# IBVAP — PRODUCT REQUIREMENTS DOCUMENT (PRD)

**Project:** IBVAP — Intelligent Border Video Analytics Platform  
**SIH Problem Statement:** SIH26187  
**Document Status:** MVP Baseline — Scope Frozen  
**Primary Goal:** Build a realistic, stable, demonstrable software-defined surveillance platform over existing CCTV infrastructure.

---

# 1. PRODUCT DEFINITION

IBVAP is an AI-driven software platform that adds intelligent video analytics to **existing ordinary IP-based CCTV cameras**.

The camera continues to provide its normal video stream. IBVAP receives that stream and processes it through an AI/Computer Vision analytics layer to detect objects, track movement, analyze defined security conditions, generate alerts, and maintain an event history.

### Core proposition

> **Existing CCTV + IBVAP software = intelligent surveillance**

IBVAP does not require replacement of the existing camera with a smart camera for the MVP.

---

# 2. PROBLEM TO SOLVE

Border security forces use CCTV at:

- Border Out Posts (BOPs)
- Check Posts
- Border Roads
- Strategic locations

Conventional CCTV systems primarily provide live monitoring and recording and therefore depend heavily on continuous human observation.

Advanced capabilities such as:

- Facial Recognition Systems
- Automatic Number Plate Recognition
- intrusion detection
- object tracking
- intelligent video analytics

often require specialized hardware or proprietary systems.

IBVAP addresses this by placing the required intelligence in software over the existing CCTV video stream.

---

# 3. PRODUCT GOAL

Build a **working software-defined surveillance platform** that demonstrates that standard IP CCTV video can be converted into actionable security information using AI, Machine Learning, Computer Vision and Video Analytics.

The MVP must focus on the capabilities explicitly required by SIH26187.

---

# 4. CORE SYSTEM FLOW

```text
Existing IP CCTV
       |
       | RTSP / video stream
       v
Video Ingestion
       |
       v
AI Video Analytics
       |
       +--> Human Detection
       +--> Human Tracking
       +--> Vehicle Detection & Classification
       +--> Face Detection
       +--> ANPR
       |
       v
Security Rule Analysis
       |
       +--> Virtual Fence
       +--> Suspicious Activity
       +--> Night-Time Movement
       |
       v
Event Engine
       |
       +--> Real-Time Alert
       +--> Evidence Snapshot
       +--> Event Log
       |
       v
Operator Dashboard
```

---

# 5. TARGET USERS

## 5.1 Security Operator

The operator monitors camera feeds and receives actionable security events.

The operator needs to know:

- which camera generated the event,
- what was detected,
- where it happened in the camera view,
- when it happened,
- why the system generated the alert.

## 5.2 Administrator

The administrator configures:

- camera sources,
- analytics features,
- restricted zones,
- thresholds,
- alert settings,
- night schedule.

---

# 6. MVP FUNCTIONAL REQUIREMENTS

## FR-01 — Existing CCTV / Video Input

The platform shall accept video from standard IP-based CCTV cameras.

### Primary input
- RTSP/IP camera stream

### MVP fallback inputs
- MP4/video file
- webcam

The fallback inputs exist only so the complete system can be demonstrated and tested without depending on a physical CCTV camera.

The analytics pipeline must remain identical regardless of whether the source is RTSP, MP4 or webcam.

---

## FR-02 — Human Detection

The system shall detect humans in the video.

The video UI shall show an appropriate bounding box around detected persons.

The detection result should include where available:

- object type
- confidence
- bounding box

---

## FR-03 — Human Tracking

The system shall track detected people across frames.

Each track should receive a temporary track ID.

Tracking information shall support later rule processing such as:

- zone entry,
- time spent in zone,
- movement history.

---

## FR-04 — Vehicle Detection

The system shall detect vehicles in the video.

---

## FR-05 — Vehicle Classification

The system shall classify supported vehicle categories available from the selected pretrained model.

For the MVP, typical categories may include:

- car
- motorcycle
- bus
- truck

The platform shall not depend on training a custom vehicle model for this MVP.

---

## FR-06 — Face Detection

The system shall detect visible faces in the video.

The face region shall be shown on the video interface where appropriate.

### MVP boundary

The mandatory technical capability is **face detection**.

The MVP shall not falsely claim that face detection equals identity recognition.

Any future identity-recognition module must be treated as a separate feature.

---

## FR-07 — Automatic Number Plate Recognition (ANPR)

The system shall provide software-based ANPR.

Required logical flow:

```text
Vehicle
   ↓
Plate Detection
   ↓
Plate Crop
   ↓
Preprocessing
   ↓
OCR
   ↓
Text Normalization
   ↓
Quality / Confidence Check
   ↓
ANPR Result
```

The system should show the best readable plate result.

When the plate cannot be read reliably:

> Plate: UNREADABLE

The system shall never fabricate a plate number.

ANPR should not run OCR on every video frame. It should operate selectively on suitable vehicle tracks/frames.

---

## FR-08 — Virtual Fence Intrusion Detection

The administrator shall be able to draw a restricted area directly over the camera view.

The area shall be represented as a polygon.

Required behavior:

```text
Outside
   ↓
Enters Restricted Zone
   ↓
Intrusion Event
```

For people, the default intrusion anchor shall be the bottom-center of the bounding box.

The same object remaining inside the zone must not generate a new event every frame.

---

## FR-09 — Suspicious Activity Detection

The MVP shall provide suspicious activity detection using **clear, explainable rules**.

The MVP shall not depend on an advanced black-box behavioral prediction model.

### Required MVP rules

#### Rule A — Restricted-Zone Intrusion
A person enters a restricted zone.

#### Rule B — Loitering
A person remains in a monitored/restricted region longer than the configured threshold.

#### Rule C — Optional Unusual Movement
An unusual-movement rule may be implemented only if it is stable, explainable and testable within the MVP timeline.

Every suspicious event shall include a reason.

---

## FR-10 — Night-Time Movement Detection

The system shall detect movement during a configurable night schedule.

Example default:

```text
22:00 → 05:00
```

When a person/vehicle is detected during the configured night period, the corresponding night-movement event may be generated according to cooldown and configuration.

The MVP shall not claim physical darkness solely from the clock.

---

## FR-11 — Real-Time Alerts

The system shall generate real-time alerts for important security events.

Relevant MVP events include:

- restricted-zone intrusion
- suspicious activity
- night-time movement

An alert shall show:

- event type
- camera
- time
- object type where available
- zone where applicable
- reason
- evidence where available
- severity

Alerts shall use debounce/cooldown to prevent duplicate events.

---

## FR-12 — Event Logging

The platform shall store security events.

Minimum event information:

```text
event_id
timestamp
camera_id
event_type
severity
object_type
track_id
zone_id
confidence
reason
evidence_path
status
```

The operator shall be able to view previous events.

---

## FR-13 — Evidence Snapshot

For important security events, the system shall save an evidence snapshot associated with the event.

The MVP does not require advanced long-term evidence management.

---

## FR-14 — Operator Dashboard

The dashboard shall provide:

### Live Monitoring
- selected camera
- live video
- AI bounding boxes
- labels
- tracking IDs

### Alerts
- current/recent alerts
- severity
- camera
- event
- timestamp
- reason

### Event History
- event list
- filters
- event details
- evidence snapshot

### Camera Status
- camera name
- connected/disconnected/error state

The primary focus remains live surveillance and actionable alerts.

---

# 7. ADMINISTRATOR CONFIGURATION

The administrator shall be able to configure:

## Cameras
- camera name
- source type
- RTSP URL
- enabled/disabled
- connection test

## Analytics
- person detection
- vehicle detection
- tracking
- face detection
- ANPR
- suspicious activity
- night movement

## Zones
- zone name
- polygon
- type
- enabled/disabled

MVP zone types:

- Restricted
- Monitoring

## Thresholds
- detection confidence
- loitering duration
- alert cooldown

## Night Schedule
- start time
- end time
- enable/disable

---

# 8. ALERT SEVERITY

The MVP shall use:

- INFO
- WARNING
- HIGH
- CRITICAL

Red is reserved primarily for important/active alert states.

---

# 9. UI/UX DIRECTION

The visual design shall follow the provided black/red security-control reference.

### Palette
- near-black background
- dark charcoal surfaces/cards
- vivid red accent
- white primary text
- muted gray secondary text
- subtle light borders

### Style
- cinematic dark interface
- high contrast
- bold typography for key information
- thin geometric framing
- restrained red highlights
- minimal clutter
- technical/security-control aesthetic

### Critical UX principle

Red means attention/danger/active state. The UI should not be saturated in red.

The visual reference is a **design direction**, not a literal copy of its page layout.

---

# 10. STABILITY & LICENSING REQUIREMENT

The MVP shall avoid strong-copyleft dependencies where a practical permissive alternative exists.

### Removed from baseline
**Ultralytics YOLO11n**

Ultralytics documents YOLO11 under AGPL-3.0 and Enterprise licensing. Therefore it is **not part of the IBVAP baseline**. citeturn734993search3

### Baseline detector
**YOLOX**

Use a YOLOX implementation/checkpoint that is verified for the intended use. The project/repository is Apache-2.0, but the exact pretrained weights must still be checked and recorded individually before shipping. 

### Other baseline direction
- OpenCV for video/CV
- OpenCV YuNet for face detection
- RapidOCR for OCR
- ONNX Runtime for local inference
- FastAPI backend
- React + TypeScript + Vite frontend
- SQLite database

RapidOCR documents Apache-2.0 licensing while explicitly noting that bundled OCR model provenance/weights must be checked separately. citeturn734993search1

ONNX Runtime is MIT licensed. citeturn734993search0

### Model licensing rule

The codebase must contain a model/dependency license inventory recording for every model:

```text
model_name
purpose
source
version
weight_license
code_license
sha256
attribution_requirements
commercial_use_status
```

The project shall never assume that a model checkpoint is commercially usable merely because its surrounding code is permissively licensed.

---

# 11. NON-FUNCTIONAL REQUIREMENTS

## Reliability
- one camera failure must not crash the entire application;
- bad frames must be skipped safely;
- AI errors must be logged;
- OCR failure must return an uncertain result instead of fabricated text;
- WebSocket disconnect must not stop event processing.

## Performance
- AI inference must run in backend workers;
- API requests must not block on heavy inference;
- frame sampling should be used when appropriate;
- ANPR should be selective rather than per-frame;
- UI must remain responsive.

## Security
- camera credentials and secrets must not be hard-coded;
- secrets must not appear in logs;
- inputs must be validated;
- filesystem writes must use controlled paths.

## Cost
The MVP should use existing camera infrastructure and software-based analytics rather than requiring dedicated intelligent-camera hardware.

---

# 12. DEPLOYMENT TARGET

The MVP is designed to run on a **single local machine**.

The local deployment contains:

```text
Backend
Frontend
AI Models
SQLite Database
Evidence Storage
```

The architecture should be scalable in design, but distributed multi-machine deployment is not required for MVP.

---

# 13. EXPLICITLY OUT OF SCOPE

Do not spend MVP time on:

- custom model training
- advanced deep behavioral prediction
- large-scale biometric recognition
- weapon detection
- audio surveillance
- autonomous physical response
- border GIS automation
- military-grade certification
- replacing CCTV hardware
- full command-and-control replacement
- nationwide distributed deployment
- mobile application
- complex cloud infrastructure
- supporting every CCTV vendor/model
- production-grade multi-tenant SaaS infrastructure

---

# 14. MVP ACCEPTANCE CRITERIA

The MVP is complete only when a controlled demonstration can show:

1. Standard video source entering IBVAP.
2. Human detection.
3. Human tracking with IDs.
4. Vehicle detection.
5. Vehicle classification.
6. Face detection.
7. Number-plate detection and OCR.
8. Operator-created restricted zone.
9. Person entering restricted zone.
10. Intrusion event.
11. Suspicious activity event.
12. Night-time movement event.
13. Real-time alert.
14. Evidence snapshot.
15. Persistent event log.
16. Settings that actually affect behavior.
17. Camera/stream failure that does not crash the application.

---

# 15. CORE PRODUCT PROMISE

> **IBVAP transforms existing ordinary IP CCTV infrastructure into an intelligent surveillance network through software-based AI video analytics, providing detection, tracking, ANPR, intrusion analysis, suspicious-activity detection, night movement detection, real-time alerts and event logging without requiring dedicated smart-camera hardware.**

---

# 16. SCOPE AUTHORITY

This PRD is the **product-scope authority**.

When another document or implementation decision conflicts with this PRD:

1. Follow the official SIH26187 requirements.
2. Follow this PRD for MVP scope.
3. Do not add features merely because they are technically possible.
4. Prefer the simplest stable implementation that demonstrates the required capability.
5. Verify model/checkpoint licensing before adding it to the shipped project.
