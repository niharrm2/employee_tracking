# VisionIQ Enterprise — Automated Biometric Employee Tracking & Workplace Vision Platform

VisionIQ is a CPU-optimized, edge-vision surveillance and attendance intelligence platform. It ingests video feeds from live RTSP IP cameras or continuous local test channels, runs deep learning inference for facial biometrics (ArcFace) and object detection (YOLOv8), logs auditable sightings to an encrypted SQLite WAL database, and exposes an enterprise REST API with an interactive dark-themed operations dashboard.

---

## 🏗️ Architecture Overview

The system is engineered using a modular, decoupled architecture:

```
c:\Dev\office_track\
├── app/
│   ├── core/                      # Cross-cutting foundational modules
│   │   ├── config.py              # Strongly-typed configuration system
│   │   ├── exceptions.py          # Unified exception hierarchy (AppError)
│   │   ├── logging.py             # Correlation request_id structured logging
│   │   └── security.py            # Salted bcrypt hashing & HS256 JWT tokens
│   ├── db/                        # Data Persistence Layer
│   │   ├── connection.py          # Thread-safe SQLite connection manager with WAL mode
│   │   ├── schema.py              # DDL schema definitions & dynamic migrations
│   │   └── repositories/          # Data Access Object (DAO) pattern
│   │       ├── base.py            # Generic BaseRepository query executor
│   │       ├── employee_repo.py   # Personnel profiles & 512-dim ArcFace embeddings
│   │       ├── sighting_repo.py   # Raw camera face sightings & visitor audit
│   │       ├── attendance_repo.py # Computed shift rollups & range queries
│   │       ├── alert_repo.py      # Optical hazard alerts & acknowledgments
│   │       ├── phone_repo.py      # Unauthorized mobile phone usage detections
│   │       ├── emotion_repo.py    # Facial expression telemetry
│   │       └── settings_repo.py   # Runtime settings (RTSP URLs, streaming modes)
│   ├── services/                  # Business Logic Layer
│   │   ├── camera_svc.py          # Dynamic camera source routing & stream latency test
│   │   ├── stream_svc.py          # Multipart MJPEG live streaming engine
│   │   ├── employee_svc.py        # Biometric onboarding & reference photo storage
│   │   ├── attendance_svc.py      # Shift rollup engine with universal date parsing
│   │   ├── alert_svc.py           # Safety hazard monitoring & unknown face audit
│   │   └── export_svc.py          # CSV and Excel (.XLSX) report generator
│   ├── pipeline/                  # Asynchronous Detection Daemon
│   │   ├── runner.py              # Hot-reloading pipeline daemon with graceful shutdown
│   │   ├── scheduler.py           # Per-camera, per-feature interval scheduler
│   │   ├── frame_grabber.py       # Connect-grab-disconnect frame capture
│   │   ├── circuit_breaker.py     # Fault isolation preventing dead RTSP feed hangs
│   │   └── processors/            # Detection task handlers
│   │       ├── face_processor.py  # Face matching & unknown visitor logging
│   │       ├── phone_processor.py # Cell phone detection with employee attribution
│   │       ├── fire_smoke_processor.py # Optical smoke & fire heuristics
│   │       └── emotion_processor.py    # Emotion telemetry
│   └── api/                       # Presentation & Routing Layer
│       ├── factory.py             # FastAPI application factory (create_app)
│       ├── deps.py                # Dependency injection & multi-source auth
│       ├── middleware.py          # Request tracing & execution timing middleware
│       └── v1/                    # Versioned REST endpoints (/api/v1/ and /api/)
│           ├── auth.py            # Authentication (/login, /me)
│           ├── settings.py        # Stream source configuration & latency testing
│           ├── cameras.py         # Camera feeds & MJPEG streams
│           ├── employees.py       # Biometric enrollment & reference photos
│           ├── attendance.py      # Daily rollups & historical range queries
│           ├── alerts.py          # Incident acknowledgment & unknown faces
│           ├── live.py            # Real-time desk presence & phone detection
│           └── exports.py         # CSV/Excel attendance export downloads
├── dashboard/                     # Web Presentation Console
│   ├── static/                    # Dark Verkada/Datadog styling & JavaScript
│   └── templates/                 # Server-rendered Jinja2 HTML templates
│       ├── dashboard.html         # Live overview & telemetry counters
│       ├── cameras.html           # Live multi-camera streaming matrix
│       ├── live.html              # Real-time desk presence monitoring
│       ├── attendance.html        # Shift intelligence & historical rollups
│       ├── employees.html         # Biometric enrollment & photo lightbox
│       ├── settings.html          # RTSP vs Local video toggle console
│       └── login.html             # Secure operator authentication
├── videos/                        # 5 Pre-recorded local test video channels
├── snapshots/profiles/            # Persisted high-res biometric reference photos
├── main_api.py                    # Production FastAPI server entry point
├── main_pipeline.py               # Production Detection daemon entry point
└── config.yaml                    # System thresholds, sampling rates & camera layout
```

---

## ⚡ Key Features

- **Live RTSP Streams ↔ Local Test Video Toggle (`/settings`):**
  - Toggle between streaming directly from hardware IP cameras via RTSP or continuous looping of local MP4 files (`entrance.mp4`, `desk_phone.mp4`, `visitor.mp4`, `pantry_fire.mp4`, `pantry_break.mp4`).
  - Hot-reloads dynamically: Detection loops and live video feeds adapt immediately without restarting any service.
  - Built-in stream tester measures latency in milliseconds and verifies stream resolution.
- **Biometric Photo Enrollment & Visual Registry (`/employees`):**
  - Accepts 3–5 reference facial imagery per subject.
  - Evaluates faces with InsightFace (`buffalo_s`), averages 512-dimensional ArcFace vectors, and saves the highest-confidence reference photo to disk.
  - Visual registry includes rounded avatar thumbnails with interactive full-resolution lightbox viewer.
- **Automatic Shift Intelligence (`/attendance`):**
  - Automatically computes daily check-in, check-out, net presence duration, and late arrival flags from camera sightings.
  - Supports universal date formatting (`DD-MM-YYYY`, `YYYY-MM-DD`, `DD/MM/YYYY`).
  - Single-click CSV and formatted Excel (.XLSX) audit downloads.
- **Circuit Breaker Fault Isolation:**
  - Protects the detection engine from stalling when network cameras drop offline or experience high jitter.
- **CPU Optimization:**
  - Leverages ONNXRuntime CPU provider and CPU-quantized YOLOv8n to run smoothly without requiring dedicated GPU hardware.

---

## 🚀 Quickstart & Installation

### 1. Prerequisites
- Python 3.11+ (Windows, Linux, or macOS)
- FFmpeg installed and available in system PATH

### 2. Virtual Environment Setup
```bash
# Clone the repository
git clone https://github.com/niharrm2/employee_tracking.git
cd employee_tracking

# Create and activate virtual environment
python -m venv venv

# Windows:
venv\Scripts\activate

# Linux / macOS:
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the API Server
```bash
python main_api.py
# The web dashboard is now accessible at: http://localhost:8000
```
Default credentials:
- **Username:** `admin`
- **Password:** `admin123`

### 5. Run the Detection Pipeline Daemon
In a separate terminal (with virtual environment activated):
```bash
python main_pipeline.py
```

---

## 📹 Video Channels Included

The repository includes 5 pre-recorded high-definition video channels in `videos/`:
1. `videos/entrance.mp4` — Main reception & biometric turnstile.
2. `videos/desk_phone.mp4` — Workstation area for cell phone detection testing.
3. `videos/visitor.mp4` — Floor 2 hallway for unknown visitor logging.
4. `videos/pantry_fire.mp4` — Breakroom pantry for optical hazard alert verification.
5. `videos/pantry_break.mp4` — Lounge area for non-work zone presence tracking.

To switch any channel to a live hardware camera, open **Settings** (`http://localhost:8000/settings`), select **Live Network RTSP Streams**, enter your camera's RTSP URL (e.g. `rtsp://user:pass@192.168.1.100:554/stream1`), test the stream, and click **Apply & Save Settings**.

---

## 🔒 Security & Privacy Notice

- **Biometric Compliance:** This system collects and processes facial embeddings. Ensure compliance with regional biometric data privacy laws (GDPR, PDPA, BIPA, etc.) and obtain appropriate employee consent before production deployment.
- **Safety Heuristics:** Optical fire and smoke detections are supplementary software heuristics and must not replace certified hardware fire alarm systems.

---

## 📄 License

Proprietary — Engineered for VisionIQ Enterprise Workplace Surveillance.