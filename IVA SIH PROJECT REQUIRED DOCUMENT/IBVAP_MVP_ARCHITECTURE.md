# IBVAP — MVP ARCHITECTURE

**Project:** IBVAP — Intelligent Border Video Analytics Platform  
**SIH:** SIH26187  
**Document Status:** Architecture Baseline — MVP  
**Primary Goal:** Stable, local-first, license-aware and demonstrable implementation over existing CCTV infrastructure.

---

# 1. ARCHITECTURE DECISION

IBVAP is a **software intelligence layer between ordinary CCTV video and the operator**.

```text
EXISTING IP CCTV
      |
      | RTSP
      v
+----------------------+
| VIDEO INGESTION      |
| OpenCV + FFmpeg      |
+----------+-----------+
           |
           v
+----------------------+
| FRAME PIPELINE       |
| buffer + sampling   |
+----------+-----------+
           |
           v
+----------------------+
| OBJECT DETECTION     |
| YOLOX                 |
| person/vehicle       |
+----------+-----------+
           |
           v
+----------------------+
| TRACKING              |
| ByteTrack             |
+----------+-----------+
           |
      +----+------------------+
      |                       |
      v                       v
+-------------+       +----------------+
| FACE        |       | ANPR           |
| YuNet       |       | plate detector |
|             |       | + RapidOCR     |
+------+------+       +-------+--------+
       |                       |
       +-----------+-----------+
                   |
                   v
          +-------------------+
          | RULE ENGINE       |
          | - virtual fence   |
          | - loitering       |
          | - night movement  |
          +---------+---------+
                    |
                    v
          +-------------------+
          | EVENT ENGINE      |
          | debounce/cooldown |
          | severity          |
          | evidence snapshot |
          +---------+---------+
                    |
             +------+------+
             |             |
             v             v
       +-----------+   +-----------+
       | WebSocket |   | SQLite    |
       | Alerts    |   | Event Log |
       +-----+-----+   +-----+-----+
             |               |
             +-------+-------+
                     v
             +---------------+
             | React + TS UI |
             | Monitoring    |
             | Alerts        |
             | Events        |
             | Settings      |
             +---------------+
```

---

# 2. TECHNOLOGY STACK — FINAL MVP BASELINE

The stack is deliberately kept small. Avoid multiple competing AI/CV runtimes unless a tested requirement forces a change.

| Layer | Technology | Role |
|---|---|---|
| OS | Windows/Linux | Local demo/deployment |
| Python | 3.11.x | Backend + CV ecosystem |
| API | FastAPI | REST + WebSocket |
| Server | Uvicorn | ASGI runtime |
| Validation | Pydantic | API/config validation |
| Video/CV | OpenCV | Frame capture, image processing |
| Video decode | FFmpeg backend | RTSP/video interoperability |
| Object detection | YOLOX | Person/vehicle detection |
| Tracking | ByteTrack | Persistent object IDs |
| Face detection | OpenCV YuNet | Face detection |
| ANPR plate detection | Dedicated pretrained plate detector | Plate localization |
| OCR | RapidOCR | Plate text extraction |
| OCR runtime | ONNX Runtime | Local accelerated inference |
| Frontend | React + TypeScript | Operator dashboard |
| Frontend build | Vite | Frontend build/dev |
| Node | 24 LTS baseline | Frontend toolchain |
| Database | SQLite | Local MVP persistence |
| ORM | SQLAlchemy 2.x | DB abstraction |
| Migrations | Alembic | Schema migration |
| Realtime | WebSocket | Live alerts |
| Evidence | Local JPEG | Event snapshots |

### Licensing decision

**Ultralytics YOLO11n is removed from the baseline.**

Ultralytics documents YOLO11 under AGPL-3.0 and Enterprise licensing. It is therefore intentionally excluded from the IBVAP baseline to avoid creating an unnecessary licensing dependency for a closed-source application. citeturn734993search3

**YOLOX is the replacement direction.**

YOLOX's project is Apache-2.0; however, the exact pretrained checkpoint used by IBVAP must be checked separately and recorded in the model license inventory before shipping.

RapidOCR is Apache-2.0 at the project level and documents that the provenance/license of its underlying OCR model artifacts must also be tracked. citeturn734993search1

ONNX Runtime is MIT licensed. citeturn734993search0

---

# 3. PYTHON BASELINE

Use:

```text
Python 3.11.x
```

The backend environment must be isolated.

Do not use Python 3.13 as the default project baseline simply because it is newer.

The objective is dependency stability across:
- OpenCV
- YOLOX/PyTorch or exported runtime
- RapidOCR
- ONNX Runtime
- FastAPI

Once validated, the exact Python patch version should be pinned in project setup documentation.

---

# 4. MODEL STRATEGY

## 4.1 Detector

Use:

```text
YOLOX
```

behind an adapter interface:

```text
Detector
   |
   +-- YOLOXDetector
```

Business logic must not import YOLOX-specific APIs everywhere.

The adapter should return a normalized result:

```text
Detection
- class_id
- class_name
- confidence
- bbox
```

## 4.2 Tracking

Use:

```text
ByteTrack
```

through a tracking interface:

```text
Tracker
   |
   +-- ByteTrackTracker
```

Normalized track:

```text
Track
- track_id
- object_type
- bbox
- confidence
- centroid
- first_seen
- last_seen
- current_zone
```

---

# 5. FACE DETECTION

Use **OpenCV YuNet**.

Pipeline:

```text
Frame
  ↓
YuNet
  ↓
Face bounding boxes
  ↓
Dashboard overlay / optional FACE_DETECTED event
```

MVP capability:

**Face detection**

Not identity recognition.

---

# 6. ANPR

ANPR is intentionally separated from generic object detection.

```text
Vehicle Track
      |
      v
Plate Candidate
      |
      v
Dedicated Plate Detector
      |
      v
Plate Crop
      |
      v
Preprocessing
      |
      v
RapidOCR
      |
      v
Normalization
      |
      v
Quality Gate
      |
      v
ANPR Result
```

### OCR policy

Do not run OCR on every frame.

For each suitable tracked vehicle:
- sample periodically,
- choose frames with acceptable plate quality,
- OCR the best candidate,
- normalize text,
- deduplicate repeated readings.

Possible result:

```text
RJ14AB1234
```

or:

```text
UNREADABLE
```

Never fabricate plate text.

---

# 7. VIDEO INGESTION

Input types:

```text
RTSP/IP CCTV
      OR
MP4 Demo Video
      OR
Webcam
```

Use an abstraction:

```text
VideoSource
├── RTSPSource
├── FileSource
└── WebcamSource
```

Each source produces normalized frames for the same downstream analytics pipeline.

---

# 8. FRAME PIPELINE

The browser display rate and AI inference rate do not have to be identical.

```text
Incoming Frame
      |
      v
Frame Buffer
      |
      +--> Detection/Tracking cadence
      |
      +--> Face cadence
      |
      +--> ANPR sampling cadence
      |
      +--> Rule evaluation
      |
      v
Annotated frame + metadata
```

Heavy AI processing must not occur inside an HTTP request handler.

---

# 9. CAMERA WORKER ARCHITECTURE

Each configured camera receives an isolated worker.

```text
Camera Worker

CONNECT
   ↓
READ
   ↓
BUFFER
   ↓
INFER
   ↓
TRACK
   ↓
RULES
   ↓
PUBLISH FRAME
   ↓
REPEAT
```

On stream failure:

```text
READ FAILURE
     ↓
log error
     ↓
mark camera ERROR
     ↓
backoff
     ↓
reconnect
```

A failed camera must not terminate other camera workers or the API.

---

# 10. ZONE ENGINE

The administrator draws a polygon directly on the camera view.

Stored:

```text
zone_id
camera_id
name
zone_type
polygon_json
enabled
```

Zone types:

- RESTRICTED
- MONITORING

For a person, use the bottom-center of the bounding box as the default anchor.

```text
Bounding Box
┌──────────┐
│  Person  │
│          │
└─────●────┘
      ^
 bottom-center
```

Then perform:

```text
anchor point
     ↓
point-in-polygon
     ↓
inside / outside
```

Trigger only on a relevant state transition:

```text
OUTSIDE
   ↓
INSIDE
   ↓
INTRUSION EVENT
```

Do not emit the same intrusion event every frame.

---

# 11. RULE ENGINE

The rule engine receives normalized tracks, zones, time and settings.

```text
RuleEngine
├── IntrusionRule
├── LoiteringRule
└── NightMovementRule
```

## Intrusion

```text
outside restricted zone
          ↓
enters zone
          ↓
ZONE_INTRUSION
```

## Loitering

```text
track enters monitored/restricted zone
          ↓
start timer
          ↓
duration >= threshold
          ↓
LOITERING
```

## Night movement

```text
current time in configured night window
          +
person/vehicle detected
          ↓
NIGHT_MOVEMENT
```

Each rule returns a normalized event candidate:

```text
EventCandidate
- event_type
- severity
- camera_id
- track_id
- zone_id
- confidence
- reason
- timestamp
```

The rule engine must not know about React or WebSocket.

---

# 12. EVENT ENGINE

The Event Engine is the single component responsible for converting event candidates into actual alerts/events.

```text
Rule Candidate
     ↓
Deduplication
     ↓
Cooldown
     ↓
Severity
     ↓
Evidence Capture
     ↓
SQLite Persistence
     ↓
WebSocket Broadcast
```

This avoids creating duplicate events from every video frame.

## Event key

Recommended logical key:

```text
camera_id
event_type
track_id
zone_id
```

Apply a configurable cooldown.

---

# 13. EVENT MODEL

Minimum event fields:

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

Event types:

```text
PERSON_DETECTED
VEHICLE_DETECTED
FACE_DETECTED
ANPR_DETECTED
ZONE_INTRUSION
LOITERING
NIGHT_MOVEMENT
```

Not every detection has to become a high-priority operator alert.

---

# 14. DATABASE

Use:

```text
SQLite
```

for the MVP.

Use:

```text
SQLAlchemy 2.x
Alembic
```

Database tables:

## cameras

```text
id
name
source_type
source_uri
enabled
status
created_at
updated_at
```

## zones

```text
id
camera_id
name
zone_type
polygon_json
enabled
created_at
updated_at
```

## events

```text
id
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

## settings

```text
key
value_json
updated_at
```

Relationships:

```text
Camera
  |
  +---- Zones
  |
  +---- Events
```

Do not store image binaries in SQLite.

---

# 15. API

## Health

```http
GET /api/health
```

## Cameras

```http
GET    /api/cameras
POST   /api/cameras
PATCH  /api/cameras/{id}
DELETE /api/cameras/{id}
POST   /api/cameras/{id}/test
```

## Zones

```http
GET    /api/cameras/{id}/zones
POST   /api/cameras/{id}/zones
PATCH  /api/zones/{id}
DELETE /api/zones/{id}
```

## Events

```http
GET /api/events
GET /api/events/{id}
```

## Settings

```http
GET   /api/settings
PATCH /api/settings
```

## Realtime

```text
WS /ws/events
```

---

# 16. LIVE VIDEO DELIVERY

The browser must not connect directly to an RTSP URL.

Backend:

```text
RTSP
 ↓
OpenCV/FFmpeg
 ↓
Frame pipeline
 ↓
Annotated frames
 ↓
Browser-compatible HTTP stream
 ↓
React dashboard
```

For the MVP, use a simple **MJPEG/HTTP stream** for browser viewing rather than introducing WebRTC infrastructure unless a tested requirement later demands it.

The AI pipeline works on the backend frame buffer, not by rereading the frontend stream.

---

# 17. FRONTEND ARCHITECTURE

Use:

```text
React
TypeScript
Vite
```

Frontend responsibilities:

- dashboard rendering
- camera selection
- video display
- overlays
- alert center
- event history
- settings
- zone drawing

Frontend must not:

- run YOLOX
- run OCR
- connect directly to RTSP
- modify the SQLite database

---

# 18. UI INFORMATION ARCHITECTURE

```text
IBVAP
│
├── Dashboard
│   ├── Live Monitoring
│   ├── Active Alerts
│   └── Camera Status
│
├── Events
│   ├── Event List
│   ├── Filters
│   └── Evidence
│
└── Settings
    ├── Cameras
    ├── Analytics
    ├── Zones
    ├── Alerts
    └── Night Schedule
```

---

# 19. UI VISUAL SYSTEM

Use the supplied reference as the visual direction.

### Colors

```text
Background: near-black
Surface: dark charcoal
Accent: vivid red
Primary text: white
Secondary text: muted gray
Borders: subtle light gray
```

### Design principles

- large bold headings
- high contrast
- sparse layouts
- geometric thin-line framing
- charcoal cards
- restrained red
- security/control-room feel

Red should primarily represent:

- critical alert
- active alert
- important status
- selected/high-priority element

Do not use red for every component.

---

# 20. SETTINGS ARCHITECTURE

Settings are persistent configuration, not live event data.

Categories:

```text
Cameras
Analytics
Zones
Alerts
Night Schedule
System
```

Settings changes must be validated before persistence.

Zone coordinates are camera-view-relative.

---

# 21. EVIDENCE STORAGE

When an important event is created:

```text
event
  ↓
capture annotated frame
  ↓
JPEG
  ↓
data/evidence/YYYY/MM/DD/
  ↓
store relative path in DB
```

Avoid storing large video evidence blobs in SQLite for MVP.

---

# 22. CONFIGURATION & SECRETS

Use:

```text
.env
.env.example
```

for secrets and environment-specific configuration.

Never hard-code:
- RTSP passwords
- API keys
- credentials

Never return secrets through API responses.

Mask credentials in logs/UI.

---

# 23. MODEL LICENSE / PROVENANCE CONTROL

This is mandatory because model code licensing and weight licensing can differ.

Create:

```text
MODEL_LICENSES.md
```

and a machine-readable model manifest if practical.

For every model/checkpoint record:

```text
model_name
purpose
source_url
version
weights_file
sha256
code_license
weight_license
commercial_use_status
attribution
```

Do not download arbitrary checkpoints dynamically in production/demo startup.

Pin the exact tested model files.

---

# 24. DEPENDENCY STABILITY

After testing, pin the exact versions used for the demo.

Backend should provide a locked dependency set.

Frontend should commit its lockfile.

Do not allow the coding agent to perform unrelated dependency upgrades during feature implementation.

Do not add multiple competing AI stacks.

Baseline AI inference stack:

```text
YOLOX
OpenCV
YuNet
RapidOCR
ONNX Runtime
```

The project must keep the AI stack as small as practical.

---

# 25. GPU / CPU STRATEGY

The app must work in both environments:

```text
GPU available
      ↓
use supported accelerator

GPU unavailable
      ↓
use CPU
```

Centralize device selection.

Example status:

```text
Inference Device: NVIDIA GPU
```

or:

```text
Inference Device: CPU
```

No CUDA dependency should be required merely to start the application in CPU mode.

---

# 26. CONCURRENCY

Heavy workloads must be separated from API request handling.

Conceptually:

```text
API
 |
 +---- Camera Workers
 |
 +---- AI Inference
 |
 +---- Event Processing
 |
 +---- WebSocket Broadcast
```

For a small MVP, this can be implemented using Python worker threads/processes and queues rather than introducing a distributed task broker.

Do not add Redis/Celery unless real workload requirements demand it.

---

# 27. RELIABILITY RULES

### Camera failure
→ mark camera ERROR, retry with backoff.

### Bad frame
→ skip frame.

### AI exception
→ log error and keep worker alive/restart safely.

### OCR failure
→ low-confidence/UNREADABLE.

### Database error
→ log and surface failure; never pretend the event was persisted.

### WebSocket disconnect
→ event engine continues.

### Model loading failure
→ clear startup/configuration error.

---

# 28. TESTING ARCHITECTURE

## Unit Tests

Test:

- point-in-polygon
- anchor-point calculation
- cooldown
- loitering timer
- night schedule
- event generation
- OCR normalization
- configuration validation

## Integration Tests

Test:

- API + database
- camera worker + frame pipeline
- inference + tracking
- rules + event engine
- event engine + WebSocket

## End-to-End Demo Tests

Test:

- human detection
- human tracking
- vehicle detection/classification
- face detection
- ANPR
- zone intrusion
- loitering
- night movement
- realtime alert
- event persistence
- evidence snapshot

---

# 29. REPOSITORY STRUCTURE

```text
ibvap/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── db/
│   │   ├── models/
│   │   ├── services/
│   │   │   ├── video/
│   │   │   ├── inference/
│   │   │   ├── tracking/
│   │   │   ├── anpr/
│   │   │   ├── rules/
│   │   │   └── events/
│   │   └── main.py
│   └── tests/
├── frontend/
│   └── src/
├── models/
│   ├── detection/
│   ├── face/
│   ├── plate/
│   └── ocr/
├── configs/
├── data/
│   ├── demo/
│   └── evidence/
├── docs/
├── .env.example
├── MODEL_LICENSES.md
├── README.md
└── dependency lock files
```

---

# 30. FUTURE SCALING DIRECTION — NOT MVP

Future:

```text
CCTV
 ↓
Video Gateway
 ↓
Multiple AI Workers
 ↓
Central Event Service
 ↓
PostgreSQL/Event Store
 ↓
Command Center
```

Do not implement this distributed architecture for the MVP.

---

# 31. FINAL END-TO-END EVENT FLOW

Example:

```text
Camera BOP-03
      ↓
RTSP frame
      ↓
YOLOX detects person
      ↓
ByteTrack → Person #27
      ↓
Bottom-center anchor
      ↓
Point-in-polygon
      ↓
Inside Restricted Zone A
      ↓
IntrusionRule
      ↓
EventCandidate
      ↓
Cooldown check
      ↓
Create event
      ↓
Capture evidence
      ↓
Save SQLite record
      ↓
WebSocket broadcast
      ↓
Dashboard alert
```

Dashboard:

```text
● CRITICAL

RESTRICTED ZONE INTRUSION

Camera: BOP-03
Zone: Restricted Zone A
Object: Person #27
Time: 02:15:42
Reason: Person entered restricted zone
```

---

# 32. ARCHITECTURAL RULES FOR ANTIGRAVITY

1. Do not reintroduce Ultralytics YOLO unless the project explicitly changes its licensing strategy.
2. Do not introduce another detector framework without a documented reason.
3. Keep model integrations behind adapters.
4. Keep heavy inference outside API request handlers.
5. Keep rules independent of UI code.
6. Keep events independent of individual video frames through cooldown/debounce.
7. Keep database access behind a service/repository layer.
8. Keep secrets outside source control.
9. Pin tested dependency/model versions before final demo.
10. Do not add architecture complexity before the current phase passes its tests.
11. Treat `MODEL_LICENSES.md` as mandatory before any model is shipped.
12. Prefer a stable tested component over a newer but unvalidated alternative.

---

# 33. FINAL ARCHITECTURE PRINCIPLE

> **IBVAP receives the ordinary video stream from existing CCTV infrastructure, performs software-based AI detection and tracking, analyzes defined security conditions, and sends actionable events to the operator without requiring dedicated smart-camera hardware.**

Final pipeline:

**Existing IP CCTV → Video Ingestion → YOLOX Detection → ByteTrack Tracking → Face/ANPR → Zone & Activity Rules → Event Engine → Real-Time Alerts + Evidence → Dashboard + Event Log**
