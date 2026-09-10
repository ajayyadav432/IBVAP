# IBVAP — UI/UX AUDIT REPORT: DESIGN SYSTEM + SETTINGS MODULE

**Project:** IBVAP — Intelligent Border Video Analytics Platform  
**SIH:** SIH26187  
**Document Status:** MVP UI/UX Baseline  
**Reference:** User-provided black/red security-control visual reference  
**Scope:** Complete visual language with detailed Settings-module UX specification

---

# 1. PURPOSE

This document defines the visual and interaction standards for IBVAP.

The objective is to make the application look like a **professional intelligent border/security operations platform**, while keeping the interface practical for an operator.

The supplied visual reference establishes the direction:

> **Near-black + charcoal + vivid red + white + restrained geometric styling**

The reference is a visual inspiration, not a literal page copy.

---

# 2. UX PRINCIPLES

IBVAP is an operational surveillance tool, not a generic SaaS dashboard.

Every screen should prioritize:

1. Situation awareness
2. Fast understanding
3. Clear alerts
4. Minimal operator effort
5. Consistent configuration
6. Stable, predictable interactions

The operator should not have to search for the important information.

---

# 3. VISUAL IDENTITY

## 3.1 Overall Feel

The interface should feel:

- dark
- technical
- precise
- security-oriented
- premium
- modern
- minimal
- high contrast
- controlled

It should **not** feel:

- playful
- social-media-like
- generic enterprise blue
- overly rounded
- colorful
- cluttered

---

# 4. COLOR SYSTEM

The following palette is the baseline and may be tuned slightly during implementation to preserve contrast across screens.

## 4.1 Primary Colors

### Background
```text
#090909
```

Use for:
- application background
- dashboard canvas
- major page backgrounds

### Surface
```text
#151515
```

Use for:
- cards
- panels
- settings sections
- sidebars

### Elevated Surface
```text
#1D1D1D
```

Use for:
- modal/dialog
- hover/elevated panels
- focused configuration sections

### Primary Accent — Security Red
```text
#FF1118
```

Use for:
- critical alerts
- active alert state
- selected high-priority controls
- active navigation indicator
- important action buttons
- intrusion indicators

### White
```text
#FFFFFF
```

Use for:
- primary headings
- essential labels
- critical information

### Secondary Text
```text
#A3A3A3
```

Use for:
- supporting descriptions
- metadata
- timestamps
- helper text

### Border
```text
#2A2A2A
```

Use for:
- card borders
- dividers
- input outlines

---

# 5. COLOR USAGE RULE

Red is an **attention color**, not a decorative theme color.

Do not make every button, card or heading red.

### Normal

```text
Black
+
Charcoal
+
White
+
Gray
```

### Alert

```text
Black
+
Charcoal
+
White
+
Red
```

The sudden appearance of red should communicate:

> Something requires attention.

---

# 6. SEVERITY VISUAL LANGUAGE

MVP event severities:

```text
INFO
WARNING
HIGH
CRITICAL
```

Use restrained visual differences.

### INFO
Neutral/dim treatment.

### WARNING
Subtle warning treatment.

### HIGH
Strong emphasis.

### CRITICAL
Use IBVAP red prominently.

Do not introduce a rainbow of unrelated status colors.

---

# 7. TYPOGRAPHY

Recommended default:

```text
Inter
```

Fallback:

```text
system-ui, sans-serif
```

## Hierarchy

### Page heading
Bold / strong weight.

### Section heading
Medium-bold.

### Primary information
Medium/semibold.

### Metadata
Smaller + muted gray.

### Critical alerts
Bold + high contrast.

Avoid excessive use of uppercase.

Uppercase can be reserved for:
- status labels
- compact operational metadata
- event types
- system indicators.

---

# 8. SPACING

Use a consistent spacing scale based on:

```text
4px
8px
12px
16px
24px
32px
48px
```

Do not create random spacing values unnecessarily.

The UI should have visible breathing room.

---

# 9. BORDERS AND SHAPES

The supplied reference uses a technical/geometric visual language.

Use:

- thin borders
- subtle corner details
- restrained geometric framing
- sharp or lightly rounded corners

Avoid excessive:
- pill-shaped containers
- huge rounded cards
- decorative gradients
- glassmorphism
- heavy drop shadows.

---

# 10. ICONOGRAPHY

Use one consistent icon library.

Icons should be:

- simple
- line-based
- easy to recognize
- visually restrained

Do not mix several icon styles.

Critical events may use:
- alert/triangle icon
- intrusion icon
- person icon
- vehicle icon
- camera icon
- settings icon.

---

# 11. MAIN APPLICATION SHELL

Recommended layout:

```text
┌─────────────────────────────────────────────────────────┐
│ IBVAP                          SYSTEM OPERATIONAL       │
├───────────────┬─────────────────────────────┬───────────┤
│               │                             │           │
│ NAVIGATION    │        MAIN CONTENT         │ ALERTS    │
│               │                             │           │
│ Dashboard     │                             │ Critical  │
│ Events        │                             │ Warning   │
│ Settings      │                             │           │
│               │                             │           │
└───────────────┴─────────────────────────────┴───────────┘
```

Do not force three permanent columns on every screen if the content does not require it. The exact layout may adapt responsively.

---

# 12. DASHBOARD UX

The dashboard is the primary operational screen.

## Priority order

```text
1. Live camera
2. Active critical alerts
3. Camera status
4. Recent events
```

The operator should see the current situation immediately.

## Main video

The camera feed should be the visual focal point.

Overlay:

- person boxes
- vehicle boxes
- track IDs
- face boxes
- plate indication
- zone boundaries

Avoid excessive text over the video.

---

# 13. LIVE VIDEO OVERLAY

Example:

```text
┌────────────────────────────────────────┐
│ BOP-03                         ● LIVE   │
│                                        │
│       ┌────────────┐                   │
│       │ PERSON     │                   │
│       │ #12  94%   │                   │
│       └────────────┘                   │
│                                        │
│                 ╱────────────╲         │
│                │ RESTRICTED   │        │
│                │     ZONE     │        │
│                 ╲────────────╱         │
│                                        │
└────────────────────────────────────────┘
```

The zone outline must remain distinguishable without covering the scene.

---

# 14. ALERT CENTER UX

The active alert panel should be visible without opening another page.

Example:

```text
● CRITICAL

RESTRICTED ZONE INTRUSION
BOP-03 · North Perimeter
02:15:42

Person #12 entered restricted zone.
```

Clicking an alert should open:
- event details
- evidence
- camera reference

Do not force the operator to navigate through several layers to understand a critical alert.

---

# 15. EVENT HISTORY UX

Event history should provide:

- timestamp
- camera
- event type
- severity
- object
- reason
- evidence availability

Filters:

- camera
- event type
- severity
- date/time

Default sorting:

> newest first

Event details should be concise first, with deeper information available on demand.

---

# 16. SETTINGS MODULE — UX OBJECTIVE

Settings is where the administrator defines **how IBVAP should behave**.

The Settings module should be:

- structured
- predictable
- safe
- understandable
- low-friction

It should not expose unnecessary model internals.

---

# 17. SETTINGS INFORMATION ARCHITECTURE

```text
SETTINGS
│
├── Cameras
├── Analytics
├── Zones
├── Alerts
├── Night Schedule
└── System
```

Use a sidebar or tab navigation inside Settings.

The selected category must be visually obvious.

---

# 18. SETTINGS — CAMERAS

## Required fields

### Camera Name
Example:

```text
BOP-03 North Gate
```

### Source Type

Options:

```text
RTSP
VIDEO FILE
WEBCAM
```

RTSP is the real CCTV integration mode.

Video File/Webcam exist for MVP demonstration/testing.

### RTSP URL

Example format:

```text
rtsp://username:password@camera-address/stream
```

Passwords must be masked.

### Enabled

Toggle:

```text
ON / OFF
```

### Test Connection

Button:

```text
TEST CONNECTION
```

Result states:

```text
CONNECTED
CONNECTING
FAILED
```

Use actionable errors.

Bad:

> Connection failed.

Good:

> Could not connect to the RTSP stream. Check URL, credentials and network reachability.

---

# 19. SETTINGS — ANALYTICS

Use grouped controls.

## Detection

```text
[ON] Person Detection
[ON] Vehicle Detection
[ON] Tracking
```

## Additional Analysis

```text
[ON] Face Detection
[ON] ANPR
[ON] Suspicious Activity
[ON] Night Movement
```

Each feature needs a short explanation.

Example:

> Detects people in the selected camera stream.

Avoid descriptions such as:

> Enables YOLOX inference pipeline.

The operator should understand the purpose, not the implementation.

---

# 20. SETTINGS — THRESHOLDS

Required:

### Detection Confidence

Example:

```text
0.50
```

Provide:
- numeric input
- acceptable range
- helper text

### Loitering Duration

Example:

```text
30 seconds
```

### Alert Cooldown

Example:

```text
30 seconds
```

Purpose:

> Prevent repeated alerts for the same ongoing event.

---

# 21. SETTINGS — ZONES

This is one of the most important settings areas.

## Zone creation flow

```text
Select Camera
      ↓
Open Zone Editor
      ↓
Draw Polygon
      ↓
Enter Zone Name
      ↓
Select Type
      ↓
Save
```

## Zone types

```text
RESTRICTED
MONITORING
```

## Zone editor

```text
┌─────────────────────────────────────┐
│ Camera Preview                      │
│                                     │
│       P1────────────P2              │
│       │   ZONE     │                │
│       │             │                │
│       P4────────────P3              │
│                                     │
└─────────────────────────────────────┘

[UNDO] [CLEAR] [SAVE ZONE]
```

After saving:

```text
North Perimeter
RESTRICTED
● ENABLED
```

---

# 22. ZONE CONFIGURATION WARNING

Display a warning once during zone setup:

> **Zone coordinates are relative to this camera view. If the camera is moved, rotated or reframed, review the zone.**

This is important because the polygon is not a physical-world coordinate system.

---

# 23. SETTINGS — ALERTS

Controls:

```text
Minimum Alert Severity
Alert Cooldown
Sound Alerts
Evidence Snapshot
```

Example:

```text
Minimum Severity
[ HIGH ▼ ]

Alert Cooldown
[ 30 seconds ]

Sound
[ ON ]

Evidence Snapshot
[ ON ]
```

Use defaults that prevent excessive alert noise.

---

# 24. SETTINGS — NIGHT SCHEDULE

Simple configuration:

```text
Night Movement Detection    [ON]

Start
[22:00]

End
[05:00]
```

Explanation:

> Night movement detection uses this configured time window.

Important clarification:

> This setting defines a time window; it does not by itself determine whether the physical scene is dark.

---

# 25. SETTINGS — SYSTEM

Show operational information:

```text
IBVAP VERSION
AI MODEL
MODEL VERSION
INFERENCE DEVICE
DATABASE STATUS
SYSTEM HEALTH
```

Example:

```text
IBVAP              v1.0.0
Detector           YOLOX
Face Detector      YuNet
OCR                RapidOCR
Inference Device   NVIDIA GPU
Database           SQLite · Connected
System             Operational
```

Do not expose:
- passwords
- API secrets
- raw credential strings.

---

# 26. SAVE BEHAVIOR

Settings should not silently disappear.

Recommended pattern:

```text
changed settings
      ↓
UNSAVED CHANGES
      ↓
SAVE CHANGES
```

After successful save:

```text
✓ Settings saved
```

The UI should not claim success until the backend confirms persistence.

---

# 27. VALIDATION

Validation must happen before persistence.

Examples:

### Invalid confidence

```text
Detection confidence must be between 0 and 1.
```

### Invalid duration

```text
Loitering duration must be greater than 0 seconds.
```

### Invalid zone

```text
A zone requires at least 3 polygon points.
```

### Invalid camera source

```text
A valid RTSP URL is required for RTSP source type.
```

---

# 28. ERROR UX

Errors must be understandable.

Do not show raw stack traces to operators.

Developer logs may contain detailed exceptions.

Operator-facing message:

> **Camera connection failed**  
> The stream could not be reached. Check the camera URL and credentials.

Developer log:

```text
CAMERA_CONNECT_ERROR
exception details...
```

This separation is mandatory.

---

# 29. LOADING STATES

Every asynchronous operation needs a visible state.

Examples:

```text
Testing connection...
Saving zone...
Loading events...
Connecting camera...
```

Never show a blank panel while the application is waiting.

---

# 30. EMPTY STATES

Examples:

### No cameras

> No cameras configured. Add a camera source to begin monitoring.

### No events

> No security events recorded yet.

### No alerts

> No active alerts.

Empty states should tell the user what to do next where appropriate.

---

# 31. DESTRUCTIVE ACTIONS

Require confirmation for:

- delete camera
- delete zone
- clear event history
- reset settings

Example:

> Delete “North Perimeter”?  
> This will remove its configuration permanently.

Buttons:

```text
CANCEL     DELETE
```

Destructive action should use the red accent.

---

# 32. ACCESSIBILITY

The MVP should provide:

- keyboard-accessible controls
- visible focus indicators
- sufficient text contrast
- labels for form controls
- non-color-only status indicators
- readable text sizes
- accessible button names

A critical alert cannot be communicated through color alone.

Example:

```text
● CRITICAL
```

not merely a red card with no text.

---

# 33. RESPONSIVE BEHAVIOR

Primary target:

> Desktop/laptop operator display.

Do not over-optimize for mobile.

However:
- layouts must not overflow,
- settings forms should remain usable at smaller widths,
- tables should support horizontal handling where required,
- video should preserve aspect ratio.

---

# 34. MICRO-INTERACTIONS

Keep motion restrained.

Allowed:
- alert arrival animation
- subtle hover state
- button loading
- status transition
- panel expansion

Avoid:
- excessive page transitions
- bouncing cards
- decorative animations
- constant flashing

Critical alerts can briefly pulse once when first generated, but must not continuously flash.

---

# 35. COMPONENT CONSISTENCY

The same component type must look and behave consistently.

Examples:

Every toggle:
- same geometry
- same active behavior
- same disabled appearance

Every input:
- same border
- same focus treatment
- same label positioning

Every alert:
- same hierarchy
- same metadata pattern

---

# 36. SETTINGS UX ACCEPTANCE CRITERIA

The Settings module is complete when:

- [ ] Camera can be added.
- [ ] RTSP credentials are masked.
- [ ] Connection can be tested.
- [ ] Camera status is shown.
- [ ] Analytics can be enabled/disabled.
- [ ] Thresholds validate correctly.
- [ ] Zones can be drawn.
- [ ] Zones can be edited.
- [ ] Zones can be deleted with confirmation.
- [ ] Night schedule can be configured.
- [ ] Alert cooldown can be configured.
- [ ] Settings persist after restart.
- [ ] Invalid configuration is rejected.
- [ ] Errors are understandable.
- [ ] Unsaved changes are visible.
- [ ] UI follows the black/red/white design system.

---

# 37. DESIGN SYSTEM NON-NEGOTIABLES

Antigravity must not replace this style with a generic dashboard template.

Do NOT introduce as the primary theme:

- blue enterprise dashboards
- purple gradients
- rainbow status chips
- glassmorphism-heavy cards
- excessive rounded corners
- oversized shadows
- excessive emoji
- decorative gradients everywhere

The supplied black/red security-control aesthetic is the baseline.

---

# 38. OPERATOR-FIRST RULE

When deciding between:

### More information
and
### Faster understanding

Choose:

> **Faster understanding**

The operator should not need to read a technical manual to understand:

> what happened, where, when, and why.

---

# 39. FINAL UI/UX PRINCIPLE

The IBVAP interface should feel like:

> **a calm, high-confidence security control system that becomes visually urgent only when an actual event requires attention.**

The visual system is therefore:

**Near-black foundation + charcoal surfaces + white information + restrained geometric framing + vivid red for security attention.**

This design system applies to the Dashboard, Events, Alerts, Camera Management, Zone Editor and Settings.
