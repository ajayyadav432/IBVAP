# IBVAP — MVP IMPLEMENTATION PLAN

**Project:** IBVAP — Intelligent Border Video Analytics Platform  
**SIH Problem Statement:** SIH26187  
**Document Status:** MVP execution baseline  
**Scope Authority:** `PRD.md`  
**Architecture Authority:** `ARCHITECTURE.md`

---

# 1. PURPOSE

This document defines **exactly how IBVAP will be built**.

The implementation strategy is deliberately incremental:

> **Build → Run → Test → Fix → Lock → Move to next phase**

Antigravity must not attempt to create the entire platform in one uncontrolled generation.

Every phase has:
- a defined objective,
- concrete deliverables,
- tests,
- an exit condition.

A phase is not complete until its exit condition passes.

---

# 2. NON-NEGOTIABLE DEVELOPMENT RULES

## Rule 1 — Follow the PRD

Do not add features that are not required by the PRD.

## Rule 2 — Follow the Architecture

Do not change the architecture merely because another library appears newer.

## Rule 3 — Stability Before Novelty

Prefer the tested, pinned implementation over the newest implementation.

## Rule 4 — No Premature Optimization

Do not introduce:
- Redis
- Celery
- Kafka
- Kubernetes
- microservices
- PostgreSQL
- WebRTC

unless a real tested requirement requires them.

The MVP is local-first.

## Rule 5 — No Custom Model Training

Use tested pretrained models.

MVP baseline:
- YOLOX
- ByteTrack
- OpenCV YuNet
- dedicated pretrained plate detector
- RapidOCR
- ONNX Runtime

## Rule 6 — Model Licensing Is Mandatory

No model checkpoint may be committed or shipped until its:
- source,
- version,
- weight license,
- code license,
- commercial-use status,
- checksum

has been recorded.

## Rule 7 — Keep AI Behind Adapters

The rest of the application must not depend directly on model-specific APIs.

Examples:

```text
Detector
  └── YOLOXDetector

Tracker
  └── ByteTrackTracker

FaceDetector
  └── YuNetFaceDetector

PlateDetector
  └── SelectedPlateDetector

OCR
  └── RapidOCREngine
```

## Rule 8 — Do Not Put Heavy AI in API Requests

Inference must run in background/camera workers.

## Rule 9 — No Event Per Frame

Events must pass through:
- rule evaluation,
- deduplication,
- cooldown.

## Rule 10 — Every Feature Must Be Demonstrable

A feature is not complete because code exists.

It must have a reproducible test.

---

# 3. FINAL MVP BUILD ORDER

```text
PHASE 0  Foundation
   ↓
PHASE 1  Video Ingestion
   ↓
PHASE 2  Human + Vehicle Detection
   ↓
PHASE 3  Tracking
   ↓
PHASE 4  Face Detection
   ↓
PHASE 5  ANPR
   ↓
PHASE 6  Virtual Fence
   ↓
PHASE 7  Suspicious Activity
   ↓
PHASE 8  Night-Time Movement
   ↓
PHASE 9  Event Engine + Alerts
   ↓
PHASE 10 Event History + Evidence
   ↓
PHASE 11 Settings + Configuration
   ↓
PHASE 12 UI Polish + Integration
   ↓
PHASE 13 Stability + Demo Hardening
```

---

# 4. PHASE 0 — FOUNDATION

## Objective

Create a clean, runnable repository before adding AI.

## Deliverables

### Repository

```text
ibvap/
├── backend/
├── frontend/
├── models/
├── configs/
├── data/
├── docs/
├── tests/
├── .env.example
├── README.md
└── MODEL_LICENSES.md
```

### Backend

Create:
- Python 3.11 virtual environment
- FastAPI application
- Uvicorn runner
- Pydantic configuration
- structured logging
- health endpoint
- SQLite connection
- SQLAlchemy
- Alembic

### Frontend

Create:
- React
- TypeScript
- Vite
- Tailwind
- basic application shell

### Required endpoint

```http
GET /api/health
```

Expected response:

```json
{
  "status": "ok"
}
```

## Tests

- backend starts
- frontend starts
- health endpoint succeeds
- SQLite initializes
- migration succeeds
- frontend builds

## Exit Condition

A clean environment can start the backend and frontend using only the README instructions.

---

# 5. PHASE 1 — VIDEO INGESTION

## Objective

Create a source-independent video pipeline.

## Deliverables

Implement:

```text
VideoSource
├── RTSPSource
├── FileSource
└── WebcamSource
```

Each source returns frames through a consistent interface.

### Required behavior

- connect
- read
- buffer
- disconnect
- reconnect
- report status

### Demo input

Start with MP4.

Then validate:
- webcam
- RTSP

## Important

Do not build AI yet.

First prove that video ingestion is stable.

## Tests

### Test A — MP4
Video opens and frames are continuously available.

### Test B — Webcam
Camera opens if available.

### Test C — Invalid RTSP
Application reports a readable connection error.

### Test D — Stream failure
A failed source does not crash the application.

## Exit Condition

The same downstream pipeline can consume MP4, webcam or RTSP without changes.

---

# 6. PHASE 2 — HUMAN + VEHICLE DETECTION

## Objective

Add pretrained YOLOX detection.

## Deliverables

Implement:

```text
Detector
└── YOLOXDetector
```

Normalized result:

```text
Detection
- class_id
- class_name
- confidence
- bbox
```

Filter for required classes.

Typical classes:

```text
person
car
motorcycle
bus
truck
```

## UI

Show:

- bounding box
- class
- confidence

Example:

```text
PERSON 0.91
┌────────────┐
│            │
│    👤      │
│            │
└────────────┘
```

## Tests

Use controlled demo videos containing:
- pedestrians
- vehicles

Verify:
- person labels
- vehicle labels
- no application crash
- reasonable inference timing

## Exit Condition

Live/demonstration video shows stable person and vehicle detections.

---

# 7. PHASE 3 — TRACKING

## Objective

Add persistent track IDs using ByteTrack.

## Deliverables

Implement:

```text
Tracker
└── ByteTrackTracker
```

Normalized track:

```text
track_id
object_type
bbox
confidence
centroid
first_seen
last_seen
```

## Requirements

- stable IDs over nearby frames
- lost-track cleanup
- track lifecycle
- centroid calculation

## Tests

A moving person should retain a consistent track ID across frames wherever the tracker can maintain identity.

## Exit Condition

Tracking IDs are visible and usable by later rules.

---

# 8. PHASE 4 — FACE DETECTION

## Objective

Add visible face detection without introducing identity recognition complexity.

## Deliverables

Implement:

```text
FaceDetector
└── YuNetFaceDetector
```

Output:

```text
Face
- bbox
- confidence
```

## UI

Display face bounding boxes.

## Tests

Use controlled images/video with clear frontal/visible faces.

Verify:
- face boxes appear
- low-quality scenes do not crash
- feature can be enabled/disabled

## Exit Condition

Face detection works independently of person detection.

---

# 9. PHASE 5 — ANPR

## Objective

Build a controlled and honest ANPR pipeline.

## Deliverables

Implement:

```text
Vehicle Track
   ↓
Plate Detector
   ↓
Plate Crop
   ↓
Preprocessing
   ↓
RapidOCR
   ↓
Normalization
   ↓
Quality Gate
```

## Plate Detector

Select one dedicated pretrained plate detector.

Before integration:

Update:

```text
MODEL_LICENSES.md
```

with:
- model
- source
- version
- license
- checksum

## OCR

Use RapidOCR + ONNX Runtime.

## Optimization

Do not OCR every frame.

Use:
- tracked vehicle
- periodic sampling
- candidate quality
- result deduplication

## Result rules

Good:

```text
RJ14AB1234
```

Poor:

```text
UNREADABLE
```

Never invent plate text.

## Tests

Use controlled plate images/videos.

Test:
- clear plate
- angled plate
- blurry plate
- unreadable plate
- repeated vehicle frames

## Exit Condition

A controlled plate can be detected and OCR can produce a qualified result.

---

# 10. PHASE 6 — VIRTUAL FENCE

## Objective

Allow the administrator to define a restricted area.

## Backend

Store:

```text
zone_id
camera_id
name
zone_type
polygon
enabled
```

## Frontend

Provide polygon editing on the video view.

Actions:

- draw
- save
- cancel
- edit
- delete
- enable/disable

## Zone logic

For people:

```text
bbox
 ↓
bottom-center point
 ↓
point-in-polygon
```

## State machine

```text
OUTSIDE
   ↓
INSIDE
   ↓
INTRUSION EVENT
```

Do not fire repeatedly for every frame.

## Tests

Controlled demo:

1. person outside
2. person approaches
3. person enters
4. intrusion event appears
5. person stays inside
6. no repeated event flood

## Exit Condition

Zone intrusion can be reproduced reliably.

---

# 11. PHASE 7 — SUSPICIOUS ACTIVITY

## Objective

Implement explainable activity rules.

## Required rule 1 — Intrusion

Already produced by zone engine.

## Required rule 2 — Loitering

Track:

```text
track_id
zone_id
entry_time
current_time
duration
```

Trigger when:

```text
duration >= configured threshold
```

Example default:

```text
30 seconds
```

The exact default may be adjusted during testing.

## Optional rule 3 — Unusual Movement

Only implement if:
- stable,
- explainable,
- reproducible.

Do not add an unreliable AI behavioral model just to make the feature appear more advanced.

## Tests

### Loitering test
Person stays inside zone long enough.

Expected:

> LOITERING DETECTED

### Non-loitering test
Person passes through quickly.

Expected:

> No loitering event.

## Exit Condition

Loitering works predictably and does not produce repeated events.

---

# 12. PHASE 8 — NIGHT-TIME MOVEMENT

## Objective

Detect movement during a configured night schedule.

## Configuration

Example:

```text
22:00
05:00
```

## Logic

```text
current_time in night_window
+
person/vehicle detected
=
NIGHT_MOVEMENT candidate
```

Then pass through event cooldown.

## Important

Do not describe this as proof of darkness.

The rule is:

> movement during configured night hours.

## Tests

- configure a short test night window
- introduce a person
- verify event
- move outside configured window
- verify no night event

## Exit Condition

Night movement works using configuration rather than hard-coded assumptions.

---

# 13. PHASE 9 — EVENT ENGINE + REAL-TIME ALERTS

## Objective

Centralize event creation and realtime delivery.

## Event flow

```text
Detection
   ↓
Rule
   ↓
Event Candidate
   ↓
Deduplication
   ↓
Cooldown
   ↓
Severity
   ↓
Evidence Capture
   ↓
Database
   ↓
WebSocket
   ↓
Dashboard
```

## Event schema

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

## WebSocket

Endpoint:

```text
/ws/events
```

## UI

Live alert panel.

Example:

```text
● CRITICAL

RESTRICTED ZONE INTRUSION

Camera: BOP-03
Zone: North Perimeter
Object: Person #12
Time: 02:15:42
```

## Tests

- event reaches WebSocket
- event appears in UI
- disconnecting the browser does not stop event processing
- duplicate alert suppression works

## Exit Condition

A generated event reaches the dashboard in realtime and is not duplicated per frame.

---

# 14. PHASE 10 — EVENT HISTORY + EVIDENCE

## Objective

Make events persistent and reviewable.

## Database

Implement events table.

## Evidence

On important event:

```text
capture annotated frame
        ↓
save JPEG
        ↓
store relative path
```

Directory:

```text
data/evidence/YYYY/MM/DD/
```

## UI

Event history must support:

- chronological list
- filtering
- severity
- event type
- camera
- details
- evidence image

## Tests

1. generate event
2. refresh application
3. event remains
4. open event
5. evidence appears

## Exit Condition

Events survive restart and can be inspected.

---

# 15. PHASE 11 — SETTINGS + CONFIGURATION

## Objective

Make required controls configurable without exposing implementation complexity.

## Settings categories

```text
Cameras
Analytics
Zones
Alerts
Night Schedule
System
```

## Required controls

### Cameras
- name
- source type
- RTSP URL
- enable/disable
- test connection

### Analytics
- person detection
- vehicle detection
- tracking
- face detection
- ANPR
- suspicious activity
- night movement

### Thresholds
- detection confidence
- loitering duration
- alert cooldown

### Night
- start
- end
- enable/disable

## Important

All settings must:
- validate,
- persist,
- survive restart,
- affect actual behavior.

## Exit Condition

Changing a setting visibly changes the corresponding system behavior.

---

# 16. PHASE 12 — UI/UX INTEGRATION

## Objective

Apply the approved black/red/white visual system to the complete application.

## Visual direction

Reference:
- near-black background
- charcoal surfaces
- vivid red accent
- white primary text
- gray secondary text
- thin geometric framing
- bold typography
- security/control-room aesthetic

## Dashboard priority

```text
1. Live video
2. Critical alerts
3. Camera status
4. Recent events
```

## Do not

- use generic blue/purple SaaS styling,
- fill every surface with red,
- create excessive rounded cards,
- hide alerts in secondary pages,
- clutter the live video.

## Exit Condition

Every major screen follows the same visual language.

---

# 17. PHASE 13 — STABILITY + DEMO HARDENING

## Objective

Freeze a known-good demo build.

## Dependency freeze

Record exact:
- Python version
- package versions
- Node version
- frontend lockfile
- model versions
- model checksums

## Model freeze

No model replacement after validation without retesting the affected pipeline.

## Test suite

Run:

### Infrastructure
- backend starts
- frontend builds
- database migration

### Video
- MP4
- webcam
- RTSP where available
- reconnect

### AI
- person
- vehicle
- tracking
- face
- ANPR

### Rules
- intrusion
- loitering
- night movement

### Events
- debounce
- persistence
- WebSocket
- evidence

### Failure cases
- invalid camera
- missing model
- OCR failure
- database failure
- browser disconnect

## Demo safety

Keep one deterministic set of demo media.

Do not depend entirely on unpredictable live camera conditions.

---

# 18. DEMO SCENARIO

The SIH demo should follow one controlled narrative.

```text
START APPLICATION
      ↓
Select BOP-03
      ↓
Live CCTV feed
      ↓
Person detected
      ↓
Person #12 tracked
      ↓
Vehicle detected
      ↓
Vehicle classified
      ↓
Face detected
      ↓
Vehicle plate detected
      ↓
ANPR result shown
      ↓
Restricted zone visible
      ↓
Person enters zone
      ↓
INTRUSION ALERT
      ↓
Person remains
      ↓
LOITERING ALERT
      ↓
Night schedule demonstration
      ↓
NIGHT MOVEMENT ALERT
      ↓
Open event history
      ↓
Evidence snapshot
```

The demo should prove the requirements rather than show unrelated UI features.

---

# 19. TEST DATA PLAN

Create a `data/demo/` directory containing controlled clips/images for:

```text
person_detection.mp4
vehicle_detection.mp4
face_detection.mp4
anpr_clear.mp4
anpr_blurry.mp4
intrusion.mp4
loitering.mp4
night_movement.mp4
```

Where possible, a smaller number of carefully selected clips can cover multiple requirements.

The files must be documented so the demo is reproducible.

---

# 20. PERFORMANCE VALIDATION

The exact target depends on available hardware.

At minimum measure:

```text
Input FPS
Inference FPS
Processing latency
CPU usage
GPU usage if available
Memory usage
```

Do not claim a fixed FPS without measuring it on the final demo machine.

If performance is too slow:

1. reduce inference resolution,
2. reduce inference frequency,
3. sample ANPR less frequently,
4. use GPU if available,
5. optimize frame buffering.

Do not immediately replace the model stack.

---

# 21. FAILURE RECOVERY

When a change breaks something:

```text
STOP FEATURE WORK
       ↓
REPRODUCE
       ↓
LOG ERROR
       ↓
IDENTIFY ROOT CAUSE
       ↓
FIX
       ↓
RUN REGRESSION TEST
       ↓
RESTORE GREEN BASELINE
       ↓
CONTINUE
```

Never hide errors simply to get a clean demo.

---

# 22. DOCUMENTATION TO MAINTAIN DURING BUILD

The repository must contain:

```text
docs/
├── PRD.md
├── ARCHITECTURE.md
├── IMPLEMENTATION_PLAN.md
├── UI_UX_AUDIT_REPORT_SETTING_MODULE.md
├── TASK_TODAY.md
├── ERROR_LOG.md
├── SAFETY_NET.md
└── MODEL_LICENSES.md
```

These documents form the project's operational memory.

---

# 23. ANTIGRAVITY EXECUTION PROTOCOL

At the start of each task, Antigravity must:

1. Read `PRD.md`.
2. Read `ARCHITECTURE.md`.
3. Read this implementation plan.
4. Read `TASK_TODAY.md`.
5. Check `ERROR_LOG.md` for known issues.
6. Check `SAFETY_NET.md` for relevant guardrails.
7. Inspect the current repository state.
8. Implement only the current phase/task.
9. Run the relevant tests.
10. Report exactly what changed and what passed/failed.

Antigravity must not:
- silently change the stack,
- silently change model providers,
- silently add features,
- silently upgrade major dependencies,
- delete failing tests,
- claim tests passed without actually running them.

---

# 24. DEFINITION OF DONE — COMPLETE MVP

IBVAP is considered complete when all of the following are working in one integrated application:

```text
✓ Existing IP/RTSP input
✓ MP4 demo input
✓ Human detection
✓ Human tracking
✓ Vehicle detection
✓ Vehicle classification
✓ Face detection
✓ ANPR
✓ Virtual fence
✓ Intrusion detection
✓ Loitering
✓ Night-time movement
✓ Real-time alerts
✓ Event logging
✓ Evidence snapshot
✓ Camera management
✓ Zone management
✓ Settings
✓ Black/red/white UI
✓ Error handling
✓ Stable local deployment
✓ Reproducible demo
```

---

# 25. FINAL BUILD PRINCIPLE

The implementation priority is:

```text
CORRECTNESS
    >
STABILITY
    >
REPRODUCIBILITY
    >
SIMPLICITY
    >
VISUAL POLISH
    >
EXTRA FEATURES
```

A smaller feature set that works reliably is preferable to a larger feature set that is unstable.

---

# 26. FINAL ARCHITECTURAL PIPELINE

```text
Existing CCTV
      ↓
RTSP / Video Source
      ↓
Video Ingestion
      ↓
Frame Pipeline
      ↓
YOLOX Detection
      ↓
ByteTrack Tracking
      ├───────────────┐
      ↓               ↓
Face Detection      Vehicle Track
      |               ↓
      |          Plate Detection
      |               ↓
      |           RapidOCR
      |               ↓
      └───────┬───────┘
              ↓
         Rule Engine
        ┌─────┼─────────┐
        ↓     ↓         ↓
    Intrusion Loitering Night
        └─────┼─────────┘
              ↓
         Event Engine
              ↓
      ┌───────┼────────┐
      ↓       ↓        ↓
    Alert   Evidence  SQLite
      ↓                 ↓
  WebSocket         Event History
      ↓
React Dashboard
```

This is the implementation baseline for Antigravity.
