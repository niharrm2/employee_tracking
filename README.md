# Office Tracking System

A CPU-only, camera-based employee attendance and activity tracking system. Consumes RTSP streams via periodic frame sampling, runs AI models for face recognition and object detection, stores results in SQLite, and exposes a FastAPI backend with a Jinja2 dashboard.

---

## ⚠️ Important Notices

> **Fire/Smoke Detection** — The built-in fire and smoke detection is a **supplementary heuristic early-warning signal only**. It is **NOT a certified fire alarm** and must NOT replace physical fire detection hardware (smoke detectors, sprinkler systems, certified alarm systems). Always maintain certified fire safety equipment as the primary system.

> **Emotion Detection** — Disabled by default. Facial-expression-based emotion inference has real accuracy limitations and raises significant employee privacy, trust, and legal concerns. Enable only after consulting HR/legal and disclosing to employees. See `detectors/emotion.py` for full details.

> **Employee Privacy** — This system collects biometric data (face embeddings). Disclose its use to all employees and verify compliance with local workplace surveillance and privacy laws (GDPR, PDPA, state-level laws, etc.) before deployment.

> **Accuracy** — All metrics (presence, breaks, phone usage) are **estimates bounded by the sampling interval**. A 15-second face-recognition interval means events between samples are not captured. Do not treat results as precise logs.

---

## Features

| Feature | Default | Notes |
|---|---|---|
| Auto check-in / check-out | ✅ On | First/last sighting per day |
| Total presence window | ✅ On | check_out − check_in |
| Present/Absent status | ✅ On | Configurable min-minutes threshold |
| Late arrival flag | ✅ On | Configurable work start + grace period |
| Early leave flag | ✅ On | Configurable work end + grace period |
| Multi-camera zone presence | ✅ On | Last-seen zone per employee |
| Visitor/unknown face logging | ✅ On | Unmatched faces logged with snapshot |
| Live desk view | ✅ On | Sightings within last N minutes |
| Break tracking | ✅ On | Gaps between sightings > threshold |
| Non-work zone time | ✅ On | Cameras tagged `zone_type: non_work` |
| Phone usage detection | ✅ On | YOLOv8n, COCO class 67 |
| Fire/smoke detection | ✅ On | HSV heuristic (supplementary only) |
| Emotion detection | ❌ Off | Enable deliberately — see caveats |

---

## Requirements

- Python 3.11+
- No GPU required (CPU-only)
- FFmpeg (for RTSP capture via OpenCV's FFmpeg backend)
- ~2 GB disk for model downloads (InsightFace buffalo_s, YOLOv8n)

---

## Setup

### 1. Clone / create project directory

```bash
cd c:\Dev\office_track
```

### 2. Create virtual environment

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate
```

### 3. Install dependencies

> **Important:** Do NOT install `onnxruntime-gpu` alongside `onnxruntime` — namespace collision will break InsightFace.

```bash
pip install -r requirements.txt
```

On Windows, PyTorch CPU wheels are fetched from the extra index URL already specified in `requirements.txt`. If you encounter issues:

```bash
pip install torch==2.3.1 torchvision==0.18.1 --index-url https://download.pytorch.org/whl/cpu
```

### 4. Configure cameras

Edit `config.yaml` and update the `cameras` section with your actual RTSP URLs:

```yaml
cameras:
  - id: "entrance_cam"
    name: "Main Entrance"
    rtsp_url: "rtsp://user:password@192.168.1.10:554/stream"
    zone: "Entrance"
    zone_type: "entrance"
    enabled: true
```

### 5. Initialise the database

```bash
python -c "import database; database.init_db()"
```

---

## Enrolling Employees

Place 3–5 clear, well-lit photos of each employee (one face per photo) in a directory, then run:

```bash
python enrollment.py enroll \
    --employee-id "EMP001" \
    --name "Jane Smith" \
    --department "Engineering" \
    --photos ./photos/jane/
```

**Tips for good enrollment photos:**
- Different angles (front, slight left, slight right)
- Different lighting conditions if possible
- No sunglasses, no heavy occlusion
- Resolution: at least 640×480px

**Other enrollment commands:**

```bash
# List all enrolled employees
python enrollment.py list

# Deactivate an employee (soft-delete)
python enrollment.py deactivate --employee-id "EMP001"

# Re-enroll with new photos (replaces embedding)
python enrollment.py re-enroll --employee-id "EMP001" --photos ./photos/jane_new/
```

---

## Running the Pipeline

```bash
python pipeline.py --config config.yaml
```

The pipeline runs continuously, sampling each enabled camera at the configured intervals. Press `Ctrl+C` to stop cleanly.

**What happens on first run:**
- InsightFace `buffalo_s` model is downloaded (~100 MB) to `~/.insightface/`
- YOLOv8n weights are downloaded (~6 MB) to `~/.config/Ultralytics/`
- Default admin user `admin` / `admin123` is created (change immediately)

---

## Running the API + Dashboard

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000
```

Then open: **http://localhost:8000**

Login with: `admin` / `admin123`

**API docs (auto-generated):** http://localhost:8000/docs

### Creating additional users

```bash
# Via API (requires admin token)
curl -X POST http://localhost:8000/api/employees/users \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"username": "hr_user", "password": "secure123", "role": "hr"}'
```

---

## Running Aggregation

Aggregation converts raw sightings into the `daily_attendance` summary table. Run it at end-of-day (or schedule it via cron/Task Scheduler):

```bash
# Aggregate today
python aggregate.py

# Aggregate a specific date
python aggregate.py --date 2026-09-07

# Aggregate a date range
python aggregate.py --date 2026-09-01 --date-end 2026-09-07
```

**Schedule with cron (Linux/Mac):**
```cron
# Run daily at 11:55 PM
55 23 * * * cd /path/to/office_track && venv/bin/python aggregate.py
```

**Schedule with Windows Task Scheduler:**
```
Action: Start a program
Program: C:\Dev\office_track\venv\Scripts\python.exe
Arguments: aggregate.py
Start in: C:\Dev\office_track
```

---

## Test RTSP Stream (Local Development)

To test the full pipeline without real cameras, set up a loopback RTSP stream using a sample `.mp4` file.

### Option A: Docker Compose (easiest)

```bash
docker compose up mediamtx
```

Then push your sample video:

```bash
ffmpeg -re -stream_loop -1 -i sample.mp4 -c copy -f rtsp rtsp://localhost:8554/entrance
```

Update `config.yaml`:
```yaml
cameras:
  - id: "entrance_cam"
    rtsp_url: "rtsp://localhost:8554/entrance"
```

### Option B: mediamtx binary (no Docker)

1. Download mediamtx from https://github.com/bluenviron/mediamtx/releases
2. Run: `./mediamtx` (or `mediamtx.exe` on Windows)
3. Push stream with ffmpeg as above

### Option C: Public test streams

Several public RTSP test streams are available online for development:
```
rtsp://wowzaec2demo.streamlock.net/vod/mp4:BigBuckBunny_115k.mp4
```

---

## Docker Compose (Full Stack)

```bash
# Build and start all services
docker compose up --build

# Start only specific services
docker compose up api mediamtx

# View pipeline logs
docker compose logs -f pipeline
```

---

## Example SQL Queries

Connect to the database:
```bash
sqlite3 office_track.db
```

### Who was present today?
```sql
SELECT e.name, e.department, da.check_in, da.check_out,
       da.presence_minutes, da.status, da.late_flag
FROM daily_attendance da
JOIN employees e ON da.employee_id = e.employee_id
WHERE da.date = date('now')
ORDER BY e.name;
```

### Late arrivals this week?
```sql
SELECT e.name, da.date, da.check_in
FROM daily_attendance da
JOIN employees e ON da.employee_id = e.employee_id
WHERE da.late_flag = 1
  AND da.date >= date('now', '-7 days')
ORDER BY da.date, e.name;
```

### Monthly attendance summary (present days per employee)?
```sql
SELECT e.name, e.department,
       COUNT(*) AS total_days,
       SUM(CASE WHEN da.status='present' THEN 1 ELSE 0 END) AS present_days,
       ROUND(AVG(da.presence_minutes), 0) AS avg_presence_min
FROM daily_attendance da
JOIN employees e ON da.employee_id = e.employee_id
WHERE da.date BETWEEN '2026-09-01' AND '2026-09-30'
GROUP BY da.employee_id
ORDER BY present_days DESC;
```

### Who's been in the pantry the most?
```sql
SELECT e.name, SUM(da.non_work_zone_minutes) AS total_non_work_min
FROM daily_attendance da
JOIN employees e ON da.employee_id = e.employee_id
WHERE da.date >= date('now', '-30 days')
GROUP BY da.employee_id
ORDER BY total_non_work_min DESC
LIMIT 10;
```

### Phone detections today?
```sql
SELECT pd.timestamp, pd.camera_id, e.name, pd.confidence
FROM phone_detections pd
LEFT JOIN employees e ON pd.detected_near_employee_id = e.employee_id
WHERE pd.timestamp LIKE date('now') || '%'
ORDER BY pd.timestamp DESC;
```

### Unacknowledged fire/smoke alerts?
```sql
SELECT * FROM fire_smoke_alerts
WHERE acknowledged = 0
ORDER BY timestamp DESC;
```

### Raw sightings for a specific employee today?
```sql
SELECT s.timestamp, s.camera_id, s.zone, s.zone_type, s.confidence
FROM sightings s
WHERE s.employee_id = 'EMP001'
  AND s.timestamp LIKE date('now') || '%'
ORDER BY s.timestamp;
```

---

## Switching to PostgreSQL

1. Update `config.yaml`:
```yaml
database:
  engine: "postgresql"
  postgresql:
    host: "localhost"
    port: 5432
    database: "office_track"
    user: "office_track"
    password: "changeme"
```

2. Update `database.py`:
   - Change `sqlite3` import to `psycopg2`
   - Change `get_connection()` to use `psycopg2.connect()`
   - Replace `?` placeholders with `%s`
   - Replace `INTEGER PRIMARY KEY AUTOINCREMENT` with `SERIAL PRIMARY KEY`
   - Replace `ON CONFLICT ... DO UPDATE` with `ON CONFLICT ... DO UPDATE SET`

All query functions remain identical — only the connection layer changes.

---

## Tuning for Performance

### Too slow on your CPU?

- Increase sampling intervals in `config.yaml` (e.g., `face_recognition: 30`)
- Reduce `det_size` for faster face detection: `det_size: [320, 320]`
- Disable unused features (`phone_detection: false`, etc.)
- Run fewer cameras simultaneously

### False positives on fire/smoke?

- Increase `fire_min_area_ratio` (e.g., `0.05`) to require larger affected area
- Increase `smoke_min_area_ratio` (e.g., `0.10`)
- Or train a custom YOLOv8n on a public fire/smoke dataset and point `fire_smoke.model_path` to it

### Face recognition mismatches?

- Increase `face_match_confidence` threshold (e.g., `0.5`) for stricter matching
- Re-enroll with more/better photos
- Ensure camera resolution and lighting are adequate

---

## Project Structure

```
office_track/
├── config.yaml              # All settings
├── requirements.txt         # Pinned CPU-only dependencies
├── README.md
├── capture.py               # RTSP frame grabbing
├── database.py              # SQLite schema + queries
├── enrollment.py            # Employee enrollment CLI
├── pipeline.py              # Main scheduler loop
├── aggregate.py             # Daily attendance rollup
├── Dockerfile.api
├── Dockerfile.pipeline
├── docker-compose.yml
├── mediamtx.yml             # Test RTSP server config
├── detectors/
│   ├── face_id.py           # InsightFace buffalo_s
│   ├── phone.py             # YOLOv8n phone detection
│   ├── fire_smoke.py        # HSV heuristic + YOLOv8 extension
│   └── emotion.py           # FER (off by default)
├── api/
│   ├── main.py              # FastAPI app
│   ├── auth.py              # JWT + RBAC
│   └── routes/
│       ├── attendance.py
│       ├── employees.py
│       ├── alerts.py
│       ├── live.py
│       └── exports.py
└── dashboard/
    ├── templates/           # Jinja2 server-rendered pages
    └── static/              # CSS + JS
```
