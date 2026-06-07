# PineVision — System Summary for Outline Defense

---

## 1. System Overview

### 1.1 System Name and Purpose

**PineVision** (sub-titled *PineWatch*) is a web-based smart farm monitoring and management platform designed specifically for pineapple plantation operations. Its primary purpose is to automate the survey and assessment of pineapple crops by combining live drone video streaming with real-time artificial intelligence-powered object detection.

### 1.2 Problem Statement

Traditional pineapple field surveys are conducted manually by walking each plantation block and physically counting plants. This method is time-consuming, labour-intensive, inconsistent across surveyors, and impractical for large-scale operations. Furthermore, it provides no real-time insight into crop health, making it difficult for farm managers to detect problems early and act before yield losses occur.

### 1.3 System Objectives

1. **Automate plant counting** — eliminate manual headcounts by detecting and classifying every visible pineapple from drone footage using AI.
2. **Classify crop health** — differentiate between bearing (fruit-ready), non-bearing (not yet fruiting), and non-viable (diseased or dead) plants.
3. **Provide real-time visibility** — update statistics on screen every two seconds during an active drone scan.
4. **Persist results** — store all scan outcomes in a cloud database for historical tracking and reporting.
5. **Alert farm managers** — automatically generate and resolve monitoring alerts when any measured metric crosses a defined threshold.
6. **Support role-based access** — separate interfaces and data access for farm operators (clients) and system managers (admins).

### 1.4 Target Users

| Role | Profile |
|------|---------|
| **Client** | Farm operators, agronomists, or field supervisors who conduct drone scans and review block-level crop data |
| **Admin** | System administrators, IT managers, or farm management supervisors responsible for user accounts, system-wide reporting, and audit oversight |

---

## 2. System Architecture

PineVision follows a **multi-tier web application architecture** composed of four primary layers: frontend presentation, backend application server, cloud database, and a video streaming subsystem.

```
┌──────────────────────────────────────────────────────────────────┐
│                         CLIENT BROWSER                           │
│   HTML + CSS + Bootstrap 5 + Vanilla JavaScript + Firebase SDK   │
└────────────────────────────┬─────────────────────────────────────┘
                             │  HTTP (port 5000)
┌────────────────────────────▼─────────────────────────────────────┐
│                    FLASK BACKEND SERVER                           │
│  app.py  +  drone_conn Blueprint  +  Firebase Admin SDK           │
│  Endpoints: /api/drone/* | /api/users/* | static serving          │
└──────┬──────────────────────────────────────────┬────────────────┘
       │  Firebase Admin SDK                       │  HTTP REST
┌──────▼───────────────┐              ┌────────────▼───────────────┐
│  FIREBASE (Google)   │              │      MEDIAMTX SERVER        │
│  Authentication      │              │  RTMP → HLS transcoder      │
│  Firestore NoSQL DB  │              │  RTMP port 1935             │
└──────────────────────┘              │  HLS port 8888              │
                                      │  API port 9997              │
                                      └────────────────────────────┘
                                                   ▲
                                                   │ RTMP stream
                                      ┌────────────┴───────────────┐
                                      │     DJI DRONE HARDWARE      │
                                      │  (DJI Fly app → RTMP push) │
                                      └────────────────────────────┘
```

### 2.1 Frontend Layer

The frontend is a **multi-page static web application** served by the Flask backend. It is implemented in vanilla HTML5, CSS3, and JavaScript — with no frontend framework — supported by Bootstrap 5 for responsive layout and grid utilities.

**Directory structure:**

| Path | Contents |
|------|----------|
| `frontend/pages/index.html` | Login / authentication entry point |
| `frontend/pages/client/` | 9 pages for farm operators |
| `frontend/pages/admin/` | 8 pages for administrators |
| `frontend/css/` | Custom design system (tokens, layout, components, responsive) |
| `frontend/js/` | Shared JavaScript utilities (auth, data, UI helpers) |
| `frontend/assets/` | SVG icons and images |
| `frontend/bootstrap/` | Bootstrap 5 bundled locally (not CDN) |

### 2.2 Backend Layer

The backend is a **Python Flask web server** (`backend/app.py`) running on port 5000. It serves two roles simultaneously:

1. **Static file server** — delivers all HTML, CSS, JavaScript, and asset files to the browser.
2. **REST API server** — exposes endpoints for drone control, detection management, and user administration.

The backend is organised into two primary components:

- `app.py` — main Flask application: static routing, Firebase initialization, user management API routes, and Blueprint registration.
- `backend/drone_conn/` — a Flask Blueprint module containing all drone and detection logic, registered under the `/api/drone/` URL prefix.

### 2.3 Database Layer (Firebase Firestore)

The system uses **Firebase Firestore**, a serverless NoSQL document database, as its data persistence layer. Both the frontend (via the Firebase JavaScript SDK) and the backend (via the Firebase Admin Python SDK) interact with Firestore directly.

**Primary Firestore collections:**

| Collection | Purpose |
|-----------|---------|
| `users` | User profiles, roles, permissions, and account status |
| `blocks` | Plantation block metadata and current scan statistics |
| `scans` | Individual scan session records with detection counts and timestamps |
| `monitoring_alerts` | Auto-generated and auto-resolved health threshold alerts |

### 2.4 Video Streaming Subsystem (MediaMTX)

**MediaMTX** is a standalone open-source media server (`mediamtx/mediamtx.exe`) that acts as the bridge between the drone's output format and the browser's playback capability.

- The **DJI drone** (via the DJI Fly application) pushes a live video stream using the **RTMP** protocol to MediaMTX on port 1935.
- MediaMTX converts the RTMP input to **HLS** (HTTP Live Streaming) format, served on port 8888.
- The browser's `<video>` element receives the HLS stream directly.
- The Flask backend communicates with MediaMTX via its REST API on port 9997 to verify that a stream path is active before confirming a connection to the frontend.

---

## 3. Key Features and Functionalities

### 3.1 Authentication and Role Management

Users authenticate through the **Firebase Authentication** service using email and password. Upon successful login, the Firebase JavaScript SDK issues a session token. The system reads the user's role (`admin` or `client`) from the Firestore `users` collection and routes the user to the appropriate dashboard.

The Flask backend independently verifies Firebase ID tokens on all sensitive API endpoints, checking the caller's role in Firestore before executing any administrative operation.

### 3.2 Drone Connection and Live Scan

The Drone View page (`drone-view.html`) is the operational centrepiece of the system. It manages the complete lifecycle of a drone scan:

1. **Prepare** — calls `POST /api/drone/prepare`, which auto-starts MediaMTX and returns the pre-filled RTMP URL for the local machine.
2. **Connect** — calls `POST /api/drone/connect`, which validates the RTMP URL, queries MediaMTX to confirm an active publisher, and returns the HLS playback URL.
3. **Stream** — the browser `<video>` element plays the HLS stream; a `<canvas>` overlay renders real-time bounding boxes on top.
4. **Detection** — calls `POST /api/drone/start-detection`, which initiates the YOLO+DeepSORT pipeline in a background thread.
5. **Live updates** — the backend writes detection statistics to Firestore every 2 seconds; the frontend reads these updates in real time.
6. **End Scan** — calls `POST /api/drone/stop-detection`, which finalises the scan session, computes population estimates, and triggers threshold-based alert logic.

The stream connection undergoes automatic health polling (`GET /api/drone/status` every 5 seconds) with up to three automatic reconnection attempts before transitioning to a `failed` state.

### 3.3 Video Upload Scan

As an alternative to live drone streaming, the system supports uploading a pre-recorded MP4 video for offline analysis via `POST /api/drone/upload-video`. The backend processes the video in a background thread using a deterministic sequential frame reader, ensuring identical results for repeated scans of the same footage.

### 3.4 AI-Powered Pineapple Detection

The detection engine is the core analytical component of the system.

**Model:** A custom-trained YOLOv8 (Ultralytics) model (`best.pt`) fine-tuned on pineapple plantation imagery. It classifies each detected object into one of three categories:

| Class | Meaning |
|-------|---------|
| `bearing` | Plant is carrying mature or near-mature fruit — ready for harvest |
| `non_bearing` | Plant is alive and growing but not yet producing fruit |
| `non_viable` | Plant is diseased, damaged, or dead — not expected to produce |

**Tracking:** The **DeepSORT** multi-object tracker is applied after YOLO detection. Each detected plant is assigned a persistent unique track ID that persists across frames. The system maintains a set of unique track IDs per category — if the same plant appears in 50 consecutive frames, it is counted only once. This eliminates duplicate counting, which is the primary challenge in frame-by-frame analysis of continuous video.

**Population estimation:** Upon scan completion, the system extrapolates detected counts to the full registered block population using the ratio of detected bearing vs. non-bearing plants and the total registered plant count stored in the block's Firestore document.

### 3.5 Block Management

The Blocks page (`blocks.html`) lists all plantation blocks associated with a user. Each block is stored as a Firestore document containing metadata (name, area in hectares, registered population, GPS coordinates, variety, and status).

The Block Detail page (`blocks-view.html`) presents the current scan statistics for a specific block, including bearing percentage, non-bearing percentage, non-viable rate, estimated counts, and a scan history table.

### 3.6 Automated Alert System

Upon scan completion, the backend checks the final bearing, non-bearing, and non-viable percentages against a fixed set of thresholds:

| Metric | Watch Threshold | Critical Threshold |
|--------|----------------|-------------------|
| Bearing % | Below 75% | Below 60% |
| Non-Bearing % | Above 18% | Above 25% |
| Non-Viable % | Above 10% | Above 15% |

The system uses a single optimised Firestore batch operation to create new alerts and auto-resolve any previously active alerts that are no longer triggered — all in one network round-trip.

### 3.7 Reporting and Scan History

Both client and admin users have access to a reports module that aggregates scan data from Firestore, providing historical trends and per-block summaries. The Scans page shows a chronological log of all past scan sessions with their final detection outcomes.

### 3.8 User Management (Admin)

The Admin Users page (`admin/users.html`) provides a full account lifecycle interface backed by the Flask API:
- Create new users in Firebase Authentication and Firestore simultaneously.
- Edit user profiles, roles, and permissions.
- Enable or disable user accounts (toggling both Firebase Auth status and Firestore status).
- Reset user passwords.

### 3.9 Audit and Activity Logs (Admin)

The Admin Activity (`admin/activity.html`) and Audit Logs (`admin/auditlogs.html`) pages provide a complete audit trail of system activity across all users, supporting accountability and compliance requirements.

---

## 4. Data Flow

### 4.1 Authentication Flow

```
User enters credentials (browser)
    → Firebase Auth JS SDK sends request to Firebase Identity Toolkit
    → Firebase returns ID token + user UID
    → Frontend reads user document from Firestore (role lookup)
    → Browser navigates to /client/dashboard or /admin/dashboard
```

### 4.2 Live Drone Scan Flow

```
1. User opens Drone View → POST /api/drone/prepare
       → Backend starts MediaMTX (if not running)
       → Backend detects local IP, returns RTMP URL to pre-fill

2. User clicks Connect → POST /api/drone/connect
       → Flask validates RTMP URL format
       → Flask queries MediaMTX API (port 9997): Is stream live?
       → If yes, returns HLS URL (http://HOST:8888/path/index.m3u8)

3. Browser loads HLS stream into <video> element
       → Browser polls GET /api/drone/status every 5s (health check)

4. POST /api/drone/start-detection (hls_url, block_id, user_id)
       → Flask creates scan session document in Firestore (status: active)
       → Background thread starts: HLSStreamCapture + YOLO + DeepSORT
       → Every frame: detect → track → update unique-ID sets
       → Every 2 seconds: batch write to Firestore (block stats + scan progress)
       → Frontend reads Firestore in real time → updates live counters on screen

5. User clicks End Scan → POST /api/drone/stop-detection
       → Detection thread stops
       → Final counts computed, population estimates calculated
       → Firestore batch write: scan status = completed, block stats updated
       → Threshold checks run → alerts created or resolved
```

### 4.3 Video Upload Scan Flow

```
User selects MP4 file → POST /api/drone/upload-video (multipart form)
    → File saved to temp directory
    → Background thread starts: sequential cap.read() loop
    → Every Nth frame: YOLO detection + DeepSORT tracking
    → Every 2 seconds: Firestore batch update
    → End of file: complete_scan_session() → alert threshold check
    → Temp file deleted after processing
```

### 4.4 Alert Generation Flow

```
Scan ends (live or video)
    → stop_detection() or _video_scan_loop_sequential() computes final %
    → check_thresholds_and_create_alerts() runs:
        1. Single Firestore query: fetch all open (unresolved) alerts for this block
        2. Compare current % against threshold definitions (in-memory)
        3. Build one batch: create alerts for new breaches, resolve alerts no longer triggered
        4. Commit batch (one network round-trip)
```

---

## 5. Technologies Used and Their Roles

| Technology | Role in System |
|-----------|---------------|
| **HTML5 / CSS3 / JavaScript** | Frontend presentation and user interaction |
| **Bootstrap 5** | Responsive grid layout and utility classes |
| **Python 3** | Backend application language |
| **Flask 2.3** | Web framework — HTTP routing, REST API, static file serving |
| **Flask-CORS** | Cross-origin request handling between frontend and backend |
| **Firebase Authentication** | Secure user login, session token issuance |
| **Firebase Firestore** | NoSQL cloud database — user records, blocks, scans, alerts |
| **Firebase Admin SDK (Python)** | Server-side Firestore writes and Auth token verification |
| **Firebase JS SDK** | Client-side Firestore reads and authentication in the browser |
| **YOLOv8 (Ultralytics)** | Real-time object detection — identifies and classifies pineapples per frame |
| **DeepSORT** | Multi-object tracking — assigns persistent IDs to prevent duplicate counts |
| **OpenCV (cv2)** | Video frame capture and image processing for YOLO inference |
| **PyTorch** | Deep learning runtime for YOLO and DeepSORT model inference |
| **MediaMTX** | RTMP-to-HLS stream transcoding and relay server |
| **FFmpeg / PyAV** | Video decode support library used by the HLS capture pipeline |
| **Werkzeug** | Secure file upload handling (secure_filename) |
| **Requests** | Flask backend's HTTP client for querying the MediaMTX REST API |

---

## 6. Module Interactions

The following describes how the major modules communicate with each other:

```
┌───────────────┐   Firebase JS SDK   ┌─────────────────────────┐
│   Browser UI  │◄───────────────────►│  Firebase Firestore      │
│  (HTML pages) │                     │  (real-time listeners)   │
└──────┬────────┘                     └─────────────────────────┘
       │ HTTP REST (port 5000)
┌──────▼────────────────────────────────────────────────────────┐
│                      Flask Backend (app.py)                    │
│                                                                │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │              drone_conn Blueprint                        │  │
│  │  routes.py → service.py → mediamtx.py                   │  │
│  │  routes.py → detection.py → firebase_client.py          │  │
│  │  routes.py → stream_capture.py → HLSStreamCapture       │  │
│  └─────────────────────────────────────────────────────────┘  │
│                                                                │
│  User Management Routes → firebase_admin.auth + firestore      │
└──────┬──────────────────────────────────────┬─────────────────┘
       │ Firebase Admin SDK                   │ HTTP REST (port 9997)
┌──────▼───────────────┐          ┌───────────▼──────────────────┐
│  Firebase (Google)   │          │  MediaMTX Process            │
│  Auth + Firestore    │          │  (mediamtx.exe)              │
└──────────────────────┘          └──────────────────────────────┘
```

**Key interaction patterns:**

1. **Frontend ↔ Flask** — The browser calls Flask REST endpoints for all drone and user management operations. Flask validates requests, orchestrates backend services, and returns JSON responses.

2. **Frontend ↔ Firestore (direct)** — The browser uses the Firebase JavaScript SDK for real-time data reads (live scan stats, block lists, alerts). This bypasses Flask to reduce latency on high-frequency updates.

3. **Flask ↔ Firebase Admin** — The Flask backend uses the Admin SDK for all server-side writes (scan sessions, block updates, alert creation) and for verifying Firebase ID tokens on protected endpoints.

4. **Flask ↔ MediaMTX** — The `drone_conn` module communicates with MediaMTX via its HTTP REST API on port 9997 to verify whether a stream path has an active publisher before confirming a connection.

5. **Flask ↔ YOLO/DeepSORT** — Detection runs in background threads managed by the `PineappleDetector` class. Frames are captured from the HLS stream (or MP4 file) via OpenCV, processed through the YOLO model, passed through the DeepSORT tracker, and the cumulative unique counts are written to Firestore at a configurable interval.

---

## 7. External Dependencies

| Dependency | Type | Purpose |
|-----------|------|---------|
| **Firebase (Google Cloud)** | Cloud service | Authentication, real-time NoSQL database |
| **DJI Drone + DJI Fly App** | Hardware + mobile app | Source of live RTMP video stream from the plantation |
| **MediaMTX** | Local executable | RTMP → HLS transcoding; browser cannot natively receive RTMP |
| **YOLOv8 custom model (`best.pt`)** | Trained ML model file | Pineapple detection and classification; must reside at `backend/best.pt` |
| **PyTorch (CUDA optional)** | ML runtime | Required to load and run the YOLO model; GPU acceleration optional |
| **DeepSORT (deep-sort-realtime)** | Python package | Multi-object tracking across video frames |
| **OpenCV** | Python package | Frame capture from HLS/MP4, image preprocessing for inference |
| **Firebase service account key** | Credential file | Authorises the Flask backend to perform privileged Firebase operations |

---

## 8. Real-Use Scenario (End-to-End Workflow)

The following describes a complete, realistic use of the system from start to finish:

**Scenario:** A farm operator conducts a survey of Block A to assess fruit readiness before harvest planning.

**Step 1 — Login**
The operator opens the PineVision web application in a browser. They enter their registered email and password. Firebase Authentication validates the credentials and issues a session token. The system reads the operator's role as `client` from Firestore and navigates to the client dashboard.

**Step 2 — Select Block**
The operator navigates to the Blocks page. A list of their assigned plantation blocks is loaded from Firestore. They select Block A and review its current status and registered population.

**Step 3 — Navigate to Drone View**
From the block detail page, the operator opens the Drone View. The system automatically calls the backend's `/api/drone/prepare` endpoint: MediaMTX is started (if not already running) and the RTMP connection URL is pre-filled.

**Step 4 — Connect the Drone**
The operator arms the DJI drone and starts the live stream in the DJI Fly application, which begins pushing RTMP video to MediaMTX on port 1935. In the PineVision interface, the operator clicks "Connect Drone." The backend validates the RTMP URL and queries MediaMTX to confirm an active publisher is present. Upon success, the HLS playback URL is returned and the browser begins playing the live video feed.

**Step 5 — Run the Scan**
Detection starts automatically. In the background, the Flask server captures frames from the HLS stream at one frame per second. Each frame is passed to YOLOv8, which outputs bounding boxes and class labels for every visible pineapple. DeepSORT assigns a unique persistent ID to each tracked plant. Cumulative unique counts (bearing, non-bearing, non-viable) are written to Firestore every two seconds. The operator watches the live video alongside updating statistics on screen. Bounding boxes are drawn on a transparent canvas overlay aligned with the video.

**Step 6 — End the Scan**
After completing the flight path over Block A, the operator clicks "End Scan." The detection thread is stopped. The system computes final percentages and extrapolates estimates for the full registered population of Block A. A completion record is written to the `scans` collection and the `blocks` document is updated with the latest statistics.

**Step 7 — Automatic Alerts**
The system immediately evaluates the final percentages against health thresholds. If, for example, the bearing rate is 58% (below the critical threshold of 60%), an alert is created in the `monitoring_alerts` collection and becomes visible on the client's Alerts page. If a previous "Low bearing rate" alert existed and the current reading is now satisfactory, that alert is auto-resolved in the same batch operation.

**Step 8 — Review Results**
The operator reviews the scan results on the Block Detail page: total pineapples detected, percentage breakdown by category, estimated full-plantation counts, and detection coverage. The scan also appears in the Scans history page for future reference.

**Step 9 — Admin Review**
A system administrator logs into the admin dashboard. They can view scan activity across all blocks and users, review generated alerts, inspect the audit log, and generate system-wide reports to support management decisions.

---

## 9. System Scope and Limitations

| Area | Current Status |
|------|---------------|
| Platform | Web only (no mobile application) |
| Drone hardware | Tested with DJI Fly RTMP output |
| Crop type | Designed specifically for pineapple plantations |
| Offline mode | Not supported — requires internet for Firebase |
| Multi-farm tenancy | Single-organisation deployment |
| Predictive analytics | Not implemented — historical data only |
| PDF report export | Not implemented in current version |
| Flight path automation | Not implemented — operator manually pilots drone |
| Weather integration | Not implemented |

---

## 10. Summary

PineVision is a full-stack smart agriculture platform that integrates drone video streaming, real-time AI object detection, cloud-based data persistence, and a role-separated web dashboard to automate the crop assessment process on pineapple plantations. The system covers the complete workflow from drone connection and live video ingestion, through frame-by-frame AI inference with duplicate-prevention tracking, to automated alert generation and cloud-stored reporting — replacing a time-consuming manual survey with a single drone flight and real-time data.
