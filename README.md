# IBVAP — Intelligent Border Video Analytics Platform (SIH26187)

**IBVAP** is an AI-driven, software-defined surveillance intelligence platform that augments existing IP-based CCTV cameras at border outposts, check posts, and strategic perimeters.

---

## Phase 0 — Foundation Architecture

This repository contains the Phase 0 foundation of IBVAP:
- **Modular Backend:** FastAPI, Uvicorn, Pydantic, SQLAlchemy 2.x, Alembic, SQLite, Structured Logging
- **Operator Frontend Shell:** React 18, TypeScript, Vite, Tailwind CSS with security control-room dark UI (#090909 / #151515 / #1D1D1D / #FF1118)
- **Database & Migrations:** SQLite persistence with automated Alembic schema tracking (`cameras`, `zones`, `events`, `settings`)
- **Safety & Licensing Compliance:** Ultralytics-free baseline, permissive licensing roadmap (YOLOX, ByteTrack, YuNet, RapidOCR)

---

## Directory Structure

```text
ibvap/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   └── routes.py          # REST endpoints (GET /api/health)
│   │   ├── core/
│   │   │   ├── config.py          # Pydantic Settings
│   │   │   └── logging.py         # Structured logging (SYSTEM, API, DATABASE)
│   │   ├── db/
│   │   │   ├── session.py         # SQLAlchemy engine & session factory
│   │   │   └── base.py            # Declarative Base
│   │   ├── models/
│   │   │   └── schema.py          # Camera, Zone, Event, Setting ORM tables
│   │   ├── services/              # Analytics & camera worker service modules
│   │   └── main.py                # FastAPI app entry point & lifespan
│   ├── alembic/                   # Alembic database migration scripts
│   │   └── versions/
│   │       └── 0001_initial_schema.py
│   ├── alembic.ini
│   ├── requirements.txt
│   └── tests/
│       └── test_health.py
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── Header.tsx         # Operational status header
│   │   │   └── Navigation.tsx     # Dashboard, Events, Settings sidebar
│   │   ├── pages/
│   │   │   ├── DashboardPage.tsx  # Live monitoring shell
│   │   │   ├── EventsPage.tsx     # Event history & log shell
│   │   │   └── SettingsPage.tsx   # System & analytics configuration shell
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   └── index.css
│   ├── index.html
│   ├── package.json
│   ├── tailwind.config.js
│   └── vite.config.ts
├── models/                        # Pretrained model checkpoint directory
│   ├── detection/
│   ├── face/
│   ├── plate/
│   └── ocr/
├── configs/                       # Deployment configurations
├── data/
│   ├── demo/                      # Demo MP4 test video clips
│   └── evidence/                  # JPEG snapshot evidence storage
├── docs/                          # Project specifications & PRD
├── tests/                         # Global integration & end-to-end tests
├── .env.example                   # Environment configuration template
├── README.md                      # Fresh-machine setup guide
└── MODEL_LICENSES.md              # Model & dependency license registry
```

---

## Fresh Machine Setup Instructions

### Prerequisites
- **Python:** 3.9+ (Python 3.11.x recommended)
- **Node.js:** v18+ (Node 20+ LTS recommended)
- **Git & PowerShell / Bash**

---

### Step 1: Clone and Configure Environment

```bash
# Clone the repository
git clone <repo-url>
cd prototype

# Create local environment configuration from template
cp .env.example .env
```

---

### Step 2: Backend Environment Setup & Installation

```powershell
# Navigate to backend directory
cd backend

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# Linux / macOS:
# source .venv/bin/activate

# Install backend dependencies
python -m pip install --upgrade pip
pip install -r requirements.txt
```

---

### Step 3: Database Initialization & Alembic Migrations

```powershell
# Ensure working directory is backend/
# Run database migrations to apply the initial schema
alembic upgrade head
```

This creates the SQLite database at `../data/ibvap.db` with all core tables (`cameras`, `zones`, `events`, `settings`).

---

### Step 4: Run Backend Unit & Health Tests

```powershell
# Execute pytest test suite
pytest -v
```

---

### Step 5: Start the Backend Server

```powershell
# Start Uvicorn development server on port 8000
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

---

### Step 6: Verify Health Endpoint

In a separate terminal or browser:

```powershell
# Verify API health check
curl http://127.0.0.1:8000/api/health
```

Expected output:
```json
{
  "status": "ok"
}
```

Interactive API documentation is available at `http://127.0.0.1:8000/docs`.

---

### Step 7: Frontend Setup & Startup

In a new terminal:

```powershell
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start Vite development server
npm run dev
```

Open your browser at `http://localhost:5173`.

---

### Step 8: Frontend Production Build

To test and compile the production bundle:

```powershell
cd frontend
npm run build
```

The optimized static production assets will be generated in `frontend/dist/`.

---

## Design System Palette

| Token | Hex | Role |
|---|---|---|
| Background | `#090909` | Base application background |
| Surface | `#151515` | Panels, cards, and sidebars |
| Elevated | `#1D1D1D` | Modals, active tabs, and hovered cards |
| Accent | `#FF1118` | Security Red — critical alerts & primary actions |
| Primary Text | `#FFFFFF` | Headings, critical labels |
| Secondary Text | `#A3A3A3` | Metadata, descriptions, timestamps |
| Border | `#2A2A2A` | Geometric framing & dividers |

---

## Model Licensing Compliance

IBVAP strictly observes open-source licensing compliance:
- **Ultralytics YOLO is excluded** due to AGPL-3.0 copyleft restrictions.
- **YOLOX** (Apache-2.0) is the approved object detector.
- See [`MODEL_LICENSES.md`](./MODEL_LICENSES.md) for the complete model provenance register.
