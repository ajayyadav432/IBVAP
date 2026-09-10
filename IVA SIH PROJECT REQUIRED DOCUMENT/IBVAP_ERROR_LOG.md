# IBVAP — ERROR LOG

**File:** `ERROR_LOG.md`  
**Project:** IBVAP — Intelligent Border Video Analytics Platform  
**Purpose:** Central engineering record for failures, bugs, integration issues and their permanent fixes.

---

# 1. PURPOSE

This file is not a raw terminal dump.

It is the project's **engineering memory**.

Every meaningful issue that can affect:
- development,
- integration,
- stability,
- demo reliability,
- model execution,
- video processing,
- database persistence,

should be recorded here.

The objective is:

> **Find the root cause → fix it → verify it → prevent recurrence.**

---

# 2. ERROR SEVERITY

## P0 — BLOCKER

The application or a core development path cannot continue.

Examples:
- backend does not start,
- AI model cannot load,
- application crashes on startup,
- critical demo feature completely unavailable.

## P1 — MAJOR

A major feature is broken but development can continue elsewhere.

Examples:
- ANPR pipeline fails,
- zone intrusion does not trigger,
- event persistence fails.

## P2 — MODERATE

A non-critical feature or workflow has a problem.

Examples:
- filtering bug,
- incorrect UI state,
- intermittent non-critical detection issue.

## P3 — MINOR

Cosmetic or low-impact problem.

Examples:
- spacing,
- icon alignment,
- minor label issue.

---

# 3. STATUS VALUES

```text
OPEN
INVESTIGATING
FIXED
VERIFIED
BLOCKED
WONTFIX
```

A bug should not be marked `VERIFIED` until the relevant test has actually passed.

---

# 4. ERROR ENTRY FORMAT

Use this format for every meaningful issue.

```text
## ERR-YYYYMMDD-XXX

Date:
Status:
Severity:
Component:

### Symptom

What the user/developer sees.

### Exact Error

Paste the shortest useful error output.

### Reproduction

Exact steps to reproduce.

### Expected

What should happen.

### Actual

What happens instead.

### Root Cause

Why the problem actually occurred.

### Fix

What was changed.

### Regression Test

How the fix was verified.

### Files Changed

List relevant files.

### Notes

Any remaining limitation or dependency.
```

---

# 5. ERROR ID FORMAT

Use:

```text
ERR-YYYYMMDD-XXX
```

Example:

```text
ERR-20260911-001
ERR-20260911-002
```

Never reuse an error ID.

---

# 6. IMPORTANT RULE

Do not record every harmless warning.

Record issues that:
- break functionality,
- can break functionality,
- cause unstable behavior,
- affect demo reliability,
- reveal dependency problems,
- require a code/configuration change.

---

# 7. ROOT-CAUSE RULE

Do not write:

> "Fixed by changing random package versions."

Instead identify why.

Good:

> OpenCV was loading a different FFmpeg backend than the validated environment.

Good:

> The same intrusion candidate was emitted on every inference frame because event cooldown was applied after persistence instead of before it.

Bad:

> Changed code until it worked.

The objective is reproducibility.

---

# 8. KNOWN / EXPECTED FAILURE CLASSES

These are not automatically bugs. They describe failure categories the implementation must handle gracefully.

---

## ERR-CLASS-01 — RTSP CONNECTION FAILURE

### Possible causes

- invalid RTSP URL
- incorrect credentials
- camera unreachable
- network routing issue
- unsupported stream format
- camera already at connection limit

### Required behavior

```text
CONNECT
  ↓
FAIL
  ↓
CAMERA = ERROR
  ↓
LOG
  ↓
RETRY WITH BACKOFF
```

The application must not crash.

The operator should receive a readable message.

---

## ERR-CLASS-02 — VIDEO DECODE FAILURE

### Possible causes

- corrupted stream
- unsupported codec
- bad frame
- unstable network packets

### Required behavior

Skip invalid frames where possible.

Continue processing subsequent valid frames.

Do not terminate all camera workers because of one invalid frame.

---

## ERR-CLASS-03 — MODEL LOAD FAILURE

### Possible causes

- missing model file
- corrupted model
- incompatible runtime
- wrong model path
- unsupported execution provider

### Required behavior

Fail clearly at startup or feature initialization.

Show:

> AI model could not be loaded. Check model files and environment.

Detailed diagnostics belong in developer logs.

---

## ERR-CLASS-04 — GPU/CUDA FAILURE

### Possible causes

- unavailable GPU
- driver mismatch
- incompatible CUDA runtime
- unsupported execution provider

### Required behavior

Where supported:

```text
GPU unavailable
    ↓
CPU fallback
```

CPU fallback must not silently create unusably slow behavior. The system should expose the active inference device.

---

## ERR-CLASS-05 — OCR FAILURE

### Possible causes

- blur
- glare
- low resolution
- plate angle
- occlusion
- poor crop
- OCR confidence too low

### Required behavior

Return:

```text
UNREADABLE
```

or a low-confidence result.

Never fabricate a license plate number.

---

## ERR-CLASS-06 — OCR FALSE READING

The system may produce incorrect OCR text on difficult imagery.

Required protections:

- quality gate
- character normalization
- confidence indication
- repeated-reading consistency where practical

Do not present an uncertain OCR result as guaranteed truth.

---

## ERR-CLASS-07 — TRACK ID INSTABILITY

### Possible causes

- occlusion
- detector misses
- crowded scene
- low frame rate
- poor lighting

### Required behavior

Tracking should degrade gracefully.

Do not build security logic that assumes track IDs are perfectly persistent in every situation.

---

## ERR-CLASS-08 — DUPLICATE ALERT FLOOD

### Symptom

One incident creates many alerts:

```text
Alert
Alert
Alert
Alert
...
```

### Required fix

Apply:

```text
event key
+
deduplication
+
cooldown
```

before persistent event creation/broadcast.

---

## ERR-CLASS-09 — ZONE FALSE POSITIVE

### Possible causes

- incorrect polygon
- camera moved
- wrong coordinate scaling
- wrong anchor point

### Required behavior

For person intrusion, default to:

```text
bottom-center of bounding box
```

Allow zone editing.

Warn the administrator that camera movement may invalidate the zone.

---

## ERR-CLASS-10 — LOITERING FALSE POSITIVE

### Possible causes

- unstable tracking
- incorrect entry timestamp
- wrong zone state
- clock/timer issue

### Required behavior

The timer must be associated with:

```text
track_id
+
zone_id
```

and reset appropriately when the track leaves or expires.

---

## ERR-CLASS-11 — NIGHT-MOVEMENT FALSE POSITIVE

### Possible cause

Confusing the configured clock window with actual physical darkness.

### Required rule

Night movement is based on the configured time window.

The UI must not claim:

> "Darkness detected"

unless a separate validated darkness-detection mechanism exists.

---

## ERR-CLASS-12 — WEBSOCKET DISCONNECT

### Expected behavior

If the browser disconnects:

```text
WebSocket disconnect
        ↓
UI loses realtime updates
        ↓
Backend continues event processing
        ↓
Database continues receiving events
```

A browser disconnect must not stop surveillance processing.

---

## ERR-CLASS-13 — DATABASE FAILURE

### Expected behavior

Do not silently report that an event was saved if persistence failed.

Log the failure and surface a meaningful system status.

---

## ERR-CLASS-14 — EVIDENCE WRITE FAILURE

### Possible causes

- permission denied
- disk full
- invalid path
- unavailable directory

### Required behavior

The event should record that evidence capture failed rather than pretending a snapshot exists.

---

# 9. DEPENDENCY / ENVIRONMENT ERRORS

Dependency errors are important because the project is deadline-sensitive.

Record issues such as:

- Python version incompatibility
- PyTorch/YOLOX compatibility problems
- OpenCV package conflicts
- ONNX Runtime provider mismatch
- RapidOCR dependency conflict
- Node/npm version conflict
- Vite build failure
- native package installation failure

Do not randomly downgrade packages.

First identify:

```text
Python version
OS
package version
model/runtime version
exact error
```

Then choose the smallest validated change.

---

# 10. MODEL / LICENSE ERRORS

Record any uncertainty about:

- model source
- checkpoint provenance
- checkpoint license
- code license
- commercial-use rights
- attribution requirements

The project must not ship a model whose license status is unclear.

Relevant record should also be added to:

```text
MODEL_LICENSES.md
```

---

# 11. SECURITY-RELATED ERRORS

Immediately record:

- exposed passwords
- secrets in logs
- credentials committed to Git
- unsafe file access
- unrestricted filesystem writes
- arbitrary URL access where not intended

If a secret is accidentally exposed:

1. remove it from the code/logs,
2. rotate the credential where applicable,
3. record the incident,
4. add a prevention measure.

Never paste real secrets into this file.

---

# 12. PERFORMANCE ISSUES

Record measurable problems.

Example:

```text
Input FPS: 25
Inference FPS: 4
Latency: 900 ms
CPU: 98%
RAM: 11 GB
```

Then record the smallest tested improvement.

Preferred optimization order:

```text
1. frame sampling
2. inference resolution
3. ANPR sampling frequency
4. processing concurrency
5. hardware acceleration
6. model optimization/replacement
```

Do not replace the entire architecture as the first reaction to slow inference.

---

# 13. UI / UX ERRORS

Record:
- broken state transitions
- save failures
- misleading status
- inaccessible controls
- missing loading/error states
- incorrect alert severity display
- visual confusion that can affect operator response

Do not prioritize cosmetic issues above broken surveillance behavior.

---

# 14. ANTIGRAVITY ERROR HANDLING RULES

When Antigravity encounters a meaningful error:

### Step 1
Stop and read existing related entries.

### Step 2
Reproduce.

### Step 3
Identify the root cause.

### Step 4
Apply the smallest appropriate fix.

### Step 5
Run the affected test.

### Step 6
Run relevant regression tests.

### Step 7
Update this file.

### Step 8
Only then continue feature work.

Antigravity must never:

- delete failing tests,
- hide exceptions,
- suppress all errors,
- silently replace the technology stack,
- silently upgrade dependencies,
- claim verification without running tests.

---

# 15. CURRENT ERROR REGISTER

No project-specific errors have been recorded yet.

```text
Status: GREEN
Open errors: 0
Known blockers: 0
```

This section should be updated as soon as implementation begins.

---

# 16. PRE-DEMO ERROR REVIEW

Before the SIH demonstration:

```text
[ ] No P0 errors open
[ ] No P1 errors affecting demo
[ ] All critical fixes verified
[ ] Known limitations documented
[ ] Demo machine tested
[ ] Demo video tested
[ ] AI models load successfully
[ ] Database persists events
[ ] Alerts do not flood
[ ] Camera failure is graceful
```

---

# 17. FINAL RULE

An error is not truly resolved when the terminal becomes quiet.

An error is resolved when:

```text
REPRODUCED
    ↓
ROOT CAUSE KNOWN
    ↓
FIX APPLIED
    ↓
TEST PASSED
    ↓
REGRESSION PROTECTED
```

That is the standard for the IBVAP MVP.
