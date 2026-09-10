# IBVAP — THE SAFETY NET

**Project:** IBVAP — Intelligent Border Video Analytics Platform  
**SIH:** SIH26187  
**Document Status:** MVP Safety Baseline  
**Purpose:** Protect the working prototype from scope creep, unstable changes, misleading behavior and avoidable demo failures.

---

# 1. PURPOSE

IBVAP is being built under a very short deadline.

The biggest risk is not lack of features.

The biggest risk is:

> **adding too much, changing too much, and breaking the working system before the demo.**

This document is therefore a mandatory safety layer for development.

The Safety Net defines:

- what must never be broken,
- what changes require extra care,
- what the coding agent is not allowed to do silently,
- what must be tested before continuing,
- how to recover from a failed change,
- how to keep the final demo deterministic.

---

# 2. GOLDEN RULE

At every point in development:

> **A stable working feature is more valuable than an unfinished advanced feature.**

Priority:

```text
WORKING
  >
STABLE
  >
TESTED
  >
REPRODUCIBLE
  >
POLISHED
  >
ADVANCED
```

---

# 3. MVP SCOPE LOCK

The MVP scope is defined by:

```text
PRD.md
```

The required feature set is:

```text
✓ CCTV / video input
✓ Human detection
✓ Human tracking
✓ Vehicle detection
✓ Vehicle classification
✓ Face detection
✓ ANPR
✓ Virtual fence
✓ Intrusion detection
✓ Suspicious activity
✓ Night-time movement
✓ Real-time alerts
✓ Event logging
✓ Evidence snapshot
✓ Camera management
✓ Zone configuration
✓ Settings
✓ Black/red/white UI
```

Do not add new major functionality until the above pipeline is operational.

---

# 4. FORBIDDEN MVP SCOPE CREEP

Do not start or prioritize:

- weapon detection
- audio surveillance
- advanced emotion analysis
- advanced behavioral prediction
- large-scale facial identity databases
- automatic border GIS mapping
- autonomous response actions
- drone integration
- mobile application
- cloud-native distributed infrastructure
- Kubernetes
- Kafka
- Redis/Celery
- microservice decomposition
- PostgreSQL migration
- WebRTC
- custom model training

unless an explicit architecture decision is made after the MVP is working.

---

# 5. ARCHITECTURE LOCK

The baseline architecture is:

```text
CCTV
 ↓
Video Ingestion
 ↓
YOLOX Detection
 ↓
ByteTrack
 ↓
Face Detection / ANPR
 ↓
Rule Engine
 ↓
Event Engine
 ↓
WebSocket + SQLite
 ↓
React Dashboard
```

Do not replace components casually.

Any proposed replacement must answer:

```text
Why?
What problem does it solve?
What dependencies change?
What tests must be rerun?
What licensing changes?
Will it delay the demo?
```

If the answer is not clearly beneficial:

> Do not replace it.

---

# 6. MODEL SAFETY

## Object Detection

Baseline:

```text
YOLOX
```

Do not reintroduce Ultralytics YOLO11 without an explicit licensing decision.

## Tracking

Baseline:

```text
ByteTrack
```

## Face

Baseline:

```text
OpenCV YuNet
```

## OCR

Baseline:

```text
RapidOCR + ONNX Runtime
```

## Plate Detection

Use one selected dedicated pretrained plate detector.

Before shipping the model, verify:

- source,
- exact checkpoint,
- code license,
- weight license,
- model provenance,
- commercial-use status,
- checksum.

Record all details in:

```text
MODEL_LICENSES.md
```

---

# 7. MODEL PROVENANCE SAFETY

Never assume:

```text
Apache/MIT code
=
every model weight is commercially usable
```

The exact model artifact must be checked.

The model manifest must contain:

```text
model_name
purpose
source
version
weight_file
sha256
code_license
weight_license
commercial_use_status
attribution
```

If licensing is unclear:

```text
STOP
 ↓
Do not ship the model
 ↓
Select a verified alternative
```

---

# 8. DEPENDENCY SAFETY

Once the environment is working:

```text
FREEZE IT
```

Record:

- Python version
- Node version
- package versions
- model versions
- model checksums

Commit frontend lockfiles.

Keep a locked backend dependency set.

Do not perform opportunistic:

```text
npm update
pip upgrade
major version migration
```

during feature development.

A newer version is not automatically a better version for a deadline-driven prototype.

---

# 9. CHANGE SAFETY

Before a major change:

```text
git status
git diff
```

Create a checkpoint when practical:

```text
git add .
git commit -m "checkpoint: working baseline"
```

Then make the change.

If it breaks the project:

```text
STOP
 ↓
Reproduce
 ↓
Check ERROR_LOG.md
 ↓
Fix or revert
 ↓
Restore green baseline
```

Never stack five experimental changes on top of each other.

---

# 10. DATABASE SAFETY

Database schema changes must use migrations.

Do not manually modify production/demo database files and assume the schema is updated everywhere.

Use:

```text
SQLAlchemy
+
Alembic
```

Before changing tables:

1. update model,
2. generate migration,
3. inspect migration,
4. run migration,
5. test affected queries.

Do not delete the database to hide migration problems.

---

# 11. VIDEO PIPELINE SAFETY

Video processing must be isolated from API requests.

Do not:

```text
HTTP request
   ↓
run entire AI pipeline
   ↓
return response
```

Instead:

```text
Camera Worker
   ↓
Frame Buffer
   ↓
Inference
   ↓
Rules
   ↓
Events
```

The browser must never directly connect to raw RTSP credentials.

---

# 12. CAMERA FAILURE SAFETY

Expected failure:

```text
Camera unavailable
```

Correct behavior:

```text
Camera = ERROR
   ↓
Log reason
   ↓
Retry with backoff
```

Incorrect behavior:

```text
Camera unavailable
   ↓
Entire application crashes
```

A single camera must not bring down the whole platform.

---

# 13. AI FAILURE SAFETY

For every AI component:

```text
Normal result
+
Failure result
```

must be defined.

Examples:

### Detection
No detections:

```text
[]
```

not an application crash.

### Face
No face:

```text
[]
```

### ANPR
Bad image:

```text
UNREADABLE
```

### Tracking
Track lost:

```text
remove/expire track safely
```

The UI must remain usable.

---

# 14. TRACKING SAFETY

Do not assume tracking is perfect.

Track IDs can change because of:

- occlusion
- poor lighting
- crowded scenes
- missed detections
- low frame rate

Security rules must degrade gracefully.

Do not create a critical workflow that depends on flawless identity continuity.

---

# 15. ANPR SAFETY

ANPR must be treated as an uncertain computer-vision result.

Never display:

> "Confirmed plate"

when the OCR result is uncertain.

Prefer:

```text
Plate: RJ14AB1234
Confidence: HIGH
```

or:

```text
Plate: RJ14A?1234
Confidence: LOW
```

or:

```text
Plate: UNREADABLE
```

The exact confidence presentation can be simplified for the MVP, but the system must never fabricate text.

---

# 16. FACE DETECTION SAFETY

The MVP performs:

```text
FACE DETECTION
```

Do not claim:

```text
IDENTITY VERIFIED
```

unless a separate verified identity-recognition capability exists.

Dashboard language must remain accurate.

---

# 17. ZONE SAFETY

Zones are defined relative to the camera image.

Therefore:

```text
camera moved
or
camera zoom changed
or
camera angle changed
```

may invalidate the zone.

The UI must communicate this.

Use:

> Zone coordinates are relative to this camera view. Review the zone if the camera framing changes.

For person intrusion:

```text
bottom-center of bounding box
```

is the default anchor.

---

# 18. EVENT SAFETY

Never create security events directly from raw frame detections without state management.

Correct:

```text
Detection
 ↓
Track
 ↓
Rule
 ↓
Candidate
 ↓
Deduplication
 ↓
Cooldown
 ↓
Event
```

Incorrect:

```text
Detection
 ↓
Alert every frame
```

---

# 19. ALERT FLOOD PROTECTION

Every event type capable of recurring continuously must have cooldown/debounce.

Example:

```text
02:15:00 — intrusion
02:15:01 — suppressed
02:15:02 — suppressed
...
02:15:30 — eligible again
```

The exact cooldown is configurable.

---

# 20. SUSPICIOUS ACTIVITY SAFETY

MVP suspicious activity is:

```text
EXPLAINABLE RULES
```

not:

```text
UNVERIFIED AI CLAIM
```

For example:

Good:

> Suspicious activity: Person remained in Restricted Zone A for 37 seconds.

Bad:

> AI detected criminal intent.

The system must not claim intentions it cannot technically establish.

---

# 21. NIGHT-MOVEMENT SAFETY

Night movement is based on:

```text
configured night time window
+
detected person/vehicle
```

It does not automatically mean:

```text
physical darkness
```

Do not display:

> Darkness confirmed

unless that separate capability is actually implemented and tested.

---

# 22. ALERT SEVERITY SAFETY

Severity should be based on the rule.

Do not make every detection:

```text
CRITICAL
```

Recommended conceptual behavior:

```text
Detection          → INFO
Night movement     → WARNING/HIGH
Loitering          → WARNING/HIGH
Restricted entry   → HIGH/CRITICAL
```

Exact mapping can be tuned during testing.

---

# 23. EVIDENCE SAFETY

Evidence capture must not break event creation.

If snapshot succeeds:

```text
event + evidence
```

If snapshot fails:

```text
event + evidence_error
```

Do not silently discard the event because the image could not be saved.

---

# 24. SETTINGS SAFETY

Settings must be:

```text
Validated
+
Persistent
+
Reversible
```

Do not allow invalid settings such as:

```text
negative duration
invalid confidence
empty polygon
malformed RTSP URL
```

Save only after validation.

Show unsaved changes.

Confirm destructive actions.

---

# 25. SECRET SAFETY

Never commit or display:

- RTSP passwords
- API keys
- access tokens
- database passwords

Use:

```text
.env
```

and `.env.example`.

The example file must contain placeholders, not real credentials.

Bad:

```text
RTSP_PASSWORD=myRealPassword
```

Good:

```text
RTSP_PASSWORD=your_password_here
```

---

# 26. FILESYSTEM SAFETY

Evidence and uploaded/configured files must use controlled paths.

Do not allow arbitrary filesystem writes from user input.

Use:

```text
data/evidence/
```

for event evidence.

Sanitize file names and paths.

---

# 27. FRONTEND SAFETY

The frontend should never assume an API request succeeded.

Correct:

```text
Save
 ↓
Backend response
 ↓
SUCCESS
```

If the backend fails:

```text
Save
 ↓
ERROR
 ↓
"Settings could not be saved."
```

Do not show a false success toast.

---

# 28. UI SAFETY

Never use color alone for critical state.

Bad:

```text
red = danger
green = okay
```

with no text.

Good:

```text
● CRITICAL
● CONNECTED
```

Also provide:
- readable labels,
- visible focus,
- clear errors,
- loading states,
- empty states.

---

# 29. PERFORMANCE SAFETY

Do not optimize blindly.

Measure:

```text
Input FPS
Inference FPS
Latency
CPU
GPU
Memory
```

If slow, improve in this order:

```text
1. frame sampling
2. resolution
3. ANPR sampling
4. queue/concurrency tuning
5. hardware acceleration
6. model optimization/replacement
```

Do not replace the entire stack because one test runs slowly.

---

# 30. DEMO SAFETY

The final demonstration must have at least one deterministic path.

Maintain:

```text
KNOWN-GOOD DEMO VIDEO
```

and ideally:

```text
KNOWN-GOOD BUILD
```

Do not rely exclusively on a live external CCTV network.

A live RTSP demo is valuable, but an MP4 fallback must remain available.

---

# 31. DEMO FEATURE FALLBACKS

If a real camera is unavailable:

```text
RTSP
 ↓
MP4 fallback
```

If GPU is unavailable:

```text
GPU
 ↓
CPU fallback
```

If OCR cannot read a plate:

```text
UNREADABLE
```

If a camera fails:

```text
Camera ERROR
```

The application should fail **gracefully**, not theatrically.

---

# 32. TEST DATA SAFETY

Keep controlled assets in:

```text
data/demo/
```

Required eventual coverage:

```text
person_detection.mp4
vehicle_detection.mp4
face_detection.mp4
anpr_clear.mp4
intrusion.mp4
loitering.mp4
night_movement.mp4
```

The final selection may use fewer files if one clip demonstrates multiple features reliably.

---

# 33. PRE-DEMO FREEZE

Before the final demonstration:

```text
STOP MAJOR FEATURE DEVELOPMENT
```

Then:

1. Run full tests.
2. Run complete demo.
3. Fix only demo-impacting defects.
4. Re-run tests.
5. Freeze dependencies.
6. Freeze models.
7. Freeze configuration.
8. Create a final Git checkpoint.

After freeze, no experimental refactors.

---

# 34. PRE-DEMO CHECKLIST

## Infrastructure

```text
[ ] Backend starts
[ ] Frontend builds
[ ] Database initializes
[ ] Migrations pass
```

## Video

```text
[ ] MP4 works
[ ] RTSP tested if available
[ ] Camera errors handled
```

## AI

```text
[ ] Person detection
[ ] Person tracking
[ ] Vehicle detection
[ ] Vehicle classification
[ ] Face detection
[ ] ANPR
```

## Security Rules

```text
[ ] Virtual fence
[ ] Intrusion
[ ] Loitering
[ ] Night movement
```

## Events

```text
[ ] Realtime alert
[ ] Deduplication
[ ] Event persistence
[ ] Evidence snapshot
```

## UI

```text
[ ] Black/red/white theme
[ ] Dashboard
[ ] Alerts
[ ] Events
[ ] Settings
[ ] Loading states
[ ] Error states
```

---

# 35. ANTIGRAVITY SAFETY PROTOCOL

Before changing code:

```text
READ RELEVANT DOCS
        ↓
INSPECT CURRENT CODE
        ↓
IDENTIFY CHANGE
        ↓
MAKE SMALLEST CHANGE
        ↓
RUN TARGETED TEST
        ↓
RUN REGRESSION TEST
        ↓
UPDATE ERROR LOG IF NEEDED
```

Antigravity must not:

- rewrite the whole codebase unnecessarily,
- change frameworks silently,
- swap models silently,
- upgrade dependencies silently,
- remove tests to make the build green,
- suppress errors,
- fabricate implementation status,
- claim a feature works without executing it.

---

# 36. "DO NOT BREAK WHAT ALREADY WORKS" RULE

If:

```text
Feature A = working
Feature B = being developed
```

then changes for Feature B must not unnecessarily rewrite Feature A.

Example:

A working video pipeline must not be rewritten simply because the Settings page is being developed.

Keep feature boundaries.

---

# 37. RECOVERY PROCEDURE

If the project becomes unstable:

```text
1. STOP adding features
2. Identify last known-good commit
3. Reproduce failure
4. Record in ERROR_LOG.md
5. Fix or revert
6. Run tests
7. Restore green state
8. Continue
```

The objective is always to return to:

```text
GREEN BUILD
```

---

# 38. FINAL SAFETY GATE

Before declaring the MVP complete:

```text
NO OPEN P0 ERRORS
+
NO DEMO-BLOCKING P1 ERRORS
+
ALL REQUIRED FEATURES DEMONSTRATED
+
MODELS LICENSE-VERIFIED
+
DEPENDENCIES PINNED
+
KNOWN LIMITATIONS DOCUMENTED
```

---

# 39. FINAL PRINCIPLE

The safest IBVAP MVP is not the one with the most code.

It is the one where:

```text
Every required feature
        ↓
has a tested implementation
        ↓
has a clear fallback
        ↓
has an understandable failure mode
        ↓
can be demonstrated tomorrow
```

> **Protect the working prototype first. Add sophistication only after reliability is secured.**
