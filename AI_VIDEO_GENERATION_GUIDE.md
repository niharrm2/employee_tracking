# AI Video Generation Guide for Testing Office Tracking System

This document provides recommended AI video tools, video specifications, exact copy-paste prompts, and step-by-step testing procedures for testing all functionalities of the Office Tracking System.

---

## 1. Recommended AI Video Generators

The following generative AI video platforms offer free tiers or trial credits and generate high-quality realistic human and office scenes:

| AI Platform | Best For | Link |
|---|---|---|
| **Luma Dream Machine** | Realistic facial features, walking, natural motion | [lumalabs.ai/dream-machine](https://lumalabs.ai/dream-machine) |
| **Kling AI** | Realistic object interactions (typing, holding phones) | [klingai.com](https://klingai.com) |
| **Runway (Gen-3 Alpha / Gen-2)** | Surveillance/CCTV camera perspectives | [runwayml.com](https://runwayml.com) |
| **Pika Labs (Pika 2.0)** | Office environments, kitchen smoke/fire effects | [pika.art](https://pika.art) |
| **Hailuo AI (MiniMax)** | Facial consistency and stable lighting | [hailuoai.video](https://hailuoai.video) |

---

## 2. Video Technical Specifications

To ensure the AI models (InsightFace, YOLOv8n, and OpenCV heuristics) run smoothly:

- **Container/Codec:** `.mp4` (H.264 video codec)
- **Resolution:** `1280x720` (720p) or `1920x1080` (1080p)
- **Duration:** 5 to 15 seconds (the system uses frame sampling, so short clips are ideal)
- **Frame Rate:** 24 or 30 FPS
- **Camera Style:** Static / fixed camera angle mounted overhead (simulating CCTV)
- **Lighting:** Even, bright commercial office lighting

---

## 3. Test Video Scenarios & Exact AI Prompts

### Scenario 1: Entrance Check-In & Face Recognition
* **Target Camera:** `entrance_cam` (`zone_type: entrance`)
* **Features Tested:**
  - Auto check-in time recording (first sighting of the day)
  - Face detection & 512-dim ArcFace embedding matching
  - Entrance zone presence tracking
* **Requirements for Model:** Clear frontal face visible for at least 2–3 seconds, well-lit, no heavy occlusion.
* **Copy-Paste Prompt:**
  ```text
  High-angle office CCTV security camera footage. A modern bright corporate office lobby entrance with glass doors. A professional young woman with dark hair wearing business casual attire enters through the front door, walks towards the camera, looks directly forward at the camera for a moment, and scans a badge before walking past. Fixed camera position, clear lighting, realistic 4k surveillance footage.
  ```

---

### Scenario 2: Desk Presence & Mobile Phone Usage
* **Target Camera:** `floor1_cam` (`zone_type: work`)
* **Features Tested:**
  - Live "Who's at desk right now" occupancy
  - YOLOv8n mobile phone detection (COCO class 67)
  - Nearest-face employee attribution
* **Requirements for Model:**
  - Person's face visible at their desk.
  - A modern smartphone clearly held in hand or in front of the person.
* **Copy-Paste Prompt:**
  ```text
  Security camera angle overlooking an office desk cubicle. An office employee is sitting in an ergonomic chair in front of dual computer monitors. He picks up a modern black smartphone, holds it in both hands, scrolls and types on the screen, then places the smartphone beside his keyboard. Realistic office interior, daylight coming from window, stable CCTV camera angle.
  ```

---

### Scenario 3: Fire & Smoke Safety Alert
* **Target Camera:** `pantry_cam` (`zone_type: non_work`)
* **Features Tested:**
  - Supplementary early-warning fire detection (HSV orange/red flame heuristic)
  - Low-saturation grey smoke haze detection
  - Emergency alert logging & acknowledgment workflow
* **Requirements for Model:**
  - Noticeable orange/yellow/red flame patches.
  - Billowing grey/white smoke haze covering at least 5% of the frame.
* **Copy-Paste Prompt:**
  ```text
  CCTV security camera view of an office pantry breakroom. An electrical toaster or microwave on a kitchen counter starts emitting visible thick grey billowing smoke, followed by small orange and yellow flames spreading along the countertop. High angle, security footage timestamp on corner, realistic smoke haze filling the room.
  ```

---

### Scenario 4: Visitor / Unknown Face Logging
* **Target Camera:** `entrance_cam` or `floor2_cam`
* **Features Tested:**
  - Unknown / visitor face logging (unmatched face detection)
  - Automatic snapshot storage in `snapshots/`
  - Visitor audit trail on Alerts dashboard
* **Requirements for Model:** A human face that is **not enrolled** in the system database.
* **Copy-Paste Prompt:**
  ```text
  Office reception area security camera. A visitor wearing a casual jacket and a delivery cap walks up to the front desk reception counter, looks around looking for someone, pauses for a few seconds facing the camera, then steps aside. High angle, clear lighting, realistic surveillance video.
  ```

---

### Scenario 5: Pantry Break & Non-Work Zone Tracking
* **Target Camera:** `pantry_cam` (`zone_type: non_work`)
* **Features Tested:**
  - Time spent in non-work zones (pantry/breakroom)
  - Break duration tracking between sightings
* **Requirements for Model:** Enrolled employee hanging out in the pantry / kitchen area.
* **Copy-Paste Prompt:**
  ```text
  Office pantry and coffee station surveillance camera. An employee in a blue shirt walks in, pours coffee from an espresso machine, stands by the counter sipping coffee and chatting, then walks out. Bright kitchen lighting, fixed overhead security camera angle.
  ```

---

## 4. How to Configure & Test in the System

### Step 1: Save the Generated Videos
Create a `videos/` folder inside `c:\Dev\office_track\` and place your `.mp4` files:
```text
c:\Dev\office_track\videos\
├── entrance.mp4
├── desk_phone.mp4
└── pantry_fire.mp4
```

### Step 2: Enroll the Employee (From Video 1)
1. Play `entrance.mp4` on your computer and take 3–4 screenshots of the person's face from different frames.
2. Save the screenshots in `c:\Dev\office_track\photos\sarah\`:
   - `photo1.jpg`
   - `photo2.jpg`
   - `photo3.jpg`
3. Enroll the employee via CLI:
   ```bash
   cd c:\Dev\office_track
   venv\Scripts\python enrollment.py enroll --employee-id "EMP001" --name "Sarah Connor" --department "Engineering" --photos ./photos/sarah/
   ```
   *(Or navigate to [http://localhost:8000/employees](http://localhost:8000/employees) in your browser and use the "+ Enroll Employee" button).*

### Step 3: Configure `config.yaml`
Update `config.yaml` to point directly to your test video files:
```yaml
cameras:
  - id: "entrance_cam"
    name: "Main Entrance"
    rtsp_url: "videos/entrance.mp4"
    zone: "Entrance"
    zone_type: "entrance"
    enabled: true

  - id: "floor1_cam"
    name: "Floor 1 — Open Office"
    rtsp_url: "videos/desk_phone.mp4"
    zone: "Floor 1"
    zone_type: "work"
    enabled: true

  - id: "pantry_cam"
    name: "Pantry"
    rtsp_url: "videos/pantry_fire.mp4"
    zone: "Pantry"
    zone_type: "non_work"
    enabled: true
```

*Note: The built-in `capture.py` automatically advances through and loops your video files in real time based on wall-clock timestamps.*

### Step 4: Verify in Dashboard
Open the dashboard at **[http://localhost:8000/](http://localhost:8000/)** (login: `admin` / `admin123`):
1. **Dashboard Home:** Observe "Sarah Connor" detected and marked in office.
2. **Live View ([http://localhost:8000/live](http://localhost:8000/live)):** Observe desk presence and phone detections logged.
3. **Alerts ([http://localhost:8000/alerts](http://localhost:8000/alerts)):** Observe Fire/Smoke alerts and Unknown Visitor faces.
4. **Attendance ([http://localhost:8000/attendance](http://localhost:8000/attendance)):** Run `venv\Scripts\python aggregate.py` and see the complete daily rollup with check-in/out and presence times.
