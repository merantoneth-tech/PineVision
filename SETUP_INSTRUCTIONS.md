# PineVision - Setup Instructions

Complete guide to set up and run the real-time pineapple detection system.

---

## Prerequisites

### Software Requirements:
- **Python 3.11+** (you have Python 3.13)
- **Git** (for version control)
- **FFmpeg** (for video processing)
- **MediaMTX** (placed in `mediamtx/` — auto-started by the backend)

### Hardware Requirements:
- Computer with at least 8GB RAM (16GB recommended)
- DJI Drone with RTMP streaming capability
- Stable internet connection
- GPU optional but recommended for faster processing

---

## Installation Steps

### 1. Clone/Download the Project

```bash
cd C:\
git clone https://github.com/yourusername/pinevision.git
cd pinevision
```

---

### 2. Set Up Python Virtual Environment

```bash
cd backend
python -m venv venv
.\venv\Scripts\activate
```

**Expected output:**
```
(venv) C:\pinevision\backend>
```

---

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Expected time:** 5-10 minutes (PyTorch is large ~200MB)

**Packages installed:**
- PyTorch 2.x+cpu
- OpenCV 4.x
- Ultralytics (YOLOv8/YOLOv5)
- DeepSORT Realtime
- Firebase Admin SDK
- Flask + Flask-CORS
- Requests

---

### 4. Verify Installation

```bash
python test_imports.py
```

**Expected output:**
```
✅ PyTorch: 2.x.x+cpu
✅ OpenCV: 4.x.x
✅ Firebase Admin SDK installed
✅ DeepSORT installed
🎉 All core dependencies installed successfully!
```

---

### 5. Set Up Firebase Credentials

**You need 1 Firebase credential file:**

#### `serviceAccountKey.json`

**Download from Firebase Console:**
1. Go to: https://console.firebase.google.com/
2. Select project: **pinevision-632aa**
3. Click: ⚙️ **Project settings** → **Service accounts** tab
4. Click: **"Generate new private key"**
5. Rename downloaded file to: `serviceAccountKey.json`
6. Place in: `backend/serviceAccountKey.json`

> **Note:** `app.py` initializes Firebase using `serviceAccountKey.json` on server start.
> `detection.py` uses the same already-initialized app when run via the Flask server.
> If you run `detection.py` directly (standalone/test mode), it also falls back to `serviceAccountKey.json`.

---

### 6. Set Up Firestore Composite Index

The automated alert system requires a composite index on the `monitoring_alerts` collection.

**Create it in Firebase Console:**
1. Go to Firebase Console → **Firestore Database** → **Indexes** tab
2. Click **"Create index"** (Composite)
3. Set:
   - Collection: `monitoring_alerts`
   - Field 1: `blockId` — Ascending
   - Field 2: `resolved` — Ascending
4. Click **"Create index"** and wait for it to build (1-2 minutes)

> Without this index, threshold checks at scan completion will fail with a Firestore error.

---

### 7. Verify Firebase Connection

```bash
cd backend
.\venv\Scripts\activate
python -c "import firebase_admin; from firebase_admin import credentials, firestore; cred = credentials.Certificate('serviceAccountKey.json'); firebase_admin.initialize_app(cred); db = firestore.client(); print('✅ Firebase connected!')"
```

**Expected output:**
```
✅ Firebase connected!
```

---

### 8. Add YOLO Model

**Get `best.pt` from team lead** (or use your trained model)
- Place in: `backend/best.pt`
- File size: ~100MB
- Model classes: `bearing`, `non-bearing`, `non-viable`

**Verify model loads:**
```bash
python -c "from ultralytics import YOLO; m = YOLO('best.pt'); print('✅ YOLO model loaded!')"
```

> The detector tries Ultralytics first, then falls back to `torch.hub` if Ultralytics fails.

---

### 9. Install FFmpeg

**Windows:**
1. Download from: https://ffmpeg.org/download.html
2. Extract to: `C:\ffmpeg`
3. Add to PATH: `C:\ffmpeg\bin`
4. Verify: `ffmpeg -version`

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt-get install ffmpeg
```

---

### 10. Install MediaMTX

**Download from:** https://github.com/bluenviron/mediamtx/releases

1. Download `mediamtx_v1.x.x_windows_amd64.zip`
2. Extract to: `pinevision\mediamtx\` (so `mediamtx.exe` is at `pinevision\mediamtx\mediamtx.exe`)

> **You do not need to start MediaMTX manually.** When the user clicks "Connect Drone" in
> the web UI, the backend calls `POST /api/drone/prepare`, which auto-launches MediaMTX
> from `mediamtx\mediamtx.exe` if it isn't already running. The RTMP URL is also
> auto-detected from your machine's local IPv4 address.

---

## Running the System

### Start the Backend Server

```bash
cd backend
.\venv\Scripts\activate
python app.py
```

**Expected output:**
```
✅ Firebase connected successfully!
🚀 Starting PineVision Backend Server...
📡 Frontend: http://localhost:5000
🔥 Firebase: User Management API enabled
🚁 Drone: Endpoints available via /api/drone/*
Running on http://0.0.0.0:5000
```

**Keep this terminal open!**

---

### Open the Frontend

Navigate to: `http://localhost:5000/client/drone-view.html?blockId=YOUR_BLOCK_ID`

Replace `YOUR_BLOCK_ID` with the actual block ID from Firebase.

> The Flask server now serves the frontend. Do **not** open `file://` URLs directly.

---

### Option 1 — Connect Live Drone

**Step 1 — Click "Connect Drone"**

The frontend calls `POST /api/drone/prepare`, which:
- Auto-starts MediaMTX (if not already running)
- Detects your machine's local IPv4 address
- Pre-fills the RTMP URL: `rtmp://<YOUR_IP>:1935/pinevision_scan`

**Step 2 — Configure DJI Drone**

1. Start your DJI drone
2. Enable RTMP streaming in DJI Fly app
3. Use the pre-filled RTMP URL (e.g., `rtmp://192.168.1.5:1935/pinevision_scan`)
4. Click **"Connect"**

**Step 3 — Detection starts automatically**

Once the stream connects, detection starts and the stats panel updates in real-time:
- **Bearing %** — Pineapples with fruit
- **Non-Bearing %** — Pineapples without fruit
- **Non-Viable %** — Discolored/diseased pineapples
- **Total Count** — Total unique pineapples detected (DeepSORT prevents duplicates)

**Step 4 — End Scan**

Click **"End Scan"** when finished. The system:
1. Stops the detection loop
2. Saves final counts to Firestore (`scans` collection)
3. Updates block stats (`blocks` collection)
4. Checks alert thresholds and creates/resolves `monitoring_alerts` automatically

---

### Option 2 — Upload MP4 Video

Use a pre-recorded drone video instead of a live RTMP stream. MediaMTX is **not** required.

**Step 1 — Click "Upload MP4"**

The button appears next to "Connect Drone" in the topbar (only when no session is active).

**Step 2 — Select an MP4 file**

A file picker opens. Select any `.mp4` recording from your drone.

**Step 3 — Scan runs automatically**

- The video loads into the drone-view player and begins playing immediately.
- The backend receives the file, starts a background YOLO+DeepSORT scan (`POST /api/drone/upload-video`), and streams intermediate results to Firestore every 2 seconds.
- The stats panel updates in real-time while the video plays (counts, progress bar).
- The progress bar reflects video playback position.

**Step 4 — Scan Finished modal**

When the video ends, a **"Scan Finished"** popup shows the final summary (duration, total detected, bearing %, non-bearing %, non-viable %). Click **OK** to save and return to the block details page.

> The backend continues processing any remaining frames after the video finishes playing.
> Final counts (with all frames included) appear in the block details once processing completes.

**Cancelling early:** Click **"End Scan"** at any time during playback to stop both the video and the backend scan. Partial results are saved to Firestore.

---

### Automated Alert Thresholds

At scan completion, the system creates or auto-resolves alerts based on:

| Metric | Watch | Critical |
|--------|-------|----------|
| Bearing % | < 75% | < 60% |
| Non-Bearing % | > 18% | > 25% |
| Non-Viable % | > 10% | > 15% |

Alerts are stored in the `monitoring_alerts` Firestore collection and auto-resolved when the condition clears on the next completed scan.

---

## Testing Without Drone

Three options depending on what you have available.

---

### Option A — FFmpeg test stream via MediaMTX (recommended)

No video file needed. Pushes a synthetic test pattern directly into MediaMTX so detection sees a live stream.

**Terminal 1 — Start MediaMTX:**

```powershell
cd mediamtx
.\mediamtx.exe
```

**Terminal 2 — Push a test stream:**

```powershell
ffmpeg -re -f lavfi -i testsrc=size=640x480:rate=25 -f lavfi -i sine `
  -c:v libx264 -preset ultrafast -c:a aac `
  -f flv rtmp://localhost:1935/pinevision_scan
```

Keep this running for the duration of the test.

**Terminal 3 — Start the Flask backend:**

```powershell
cd backend
.\venv\Scripts\activate
python app.py
```

**Terminal 4 — Trigger detection:**

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/drone/start-detection" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"hls_url":"http://localhost:8888/pinevision_scan/index.m3u8","block_id":"test_block_id","user_id":"test_user","fps":1}'
```

> The detection backend automatically prefers RTSP (`rtsp://localhost:8554/pinevision_scan`) over HLS when connecting to a MediaMTX stream, which gives a stable continuous feed with no segment-boundary gaps.

**Expected output:**
```
⏳ Waiting for HLS playlist to become ready...
✅ HLS playlist ready (attempt 1)
🔄 Trying RTSP (preferred over HLS): rtsp://localhost:8554/pinevision_scan
✅ RTSP VideoCapture opened (attempt 1): rtsp://localhost:8554/pinevision_scan
⏳ Warming up stream (draining 10 buffered frames)...
🎥 Stream capture started - Processing at 1 FPS
📊 Frame 7: Total=4 (B:3, NB:1, NV:0) [+1 new]
📊 Frame 11: Total=8 (B:4, NB:4, NV:0) [+4 new]
```

---

### Option B — MP4 direct scan (no HLS, no MediaMTX)

The simplest testing mode. Can be triggered two ways:

- **Via the UI** — Click **"Upload MP4"** on the drone-view page (backend must be running). The frontend uploads the file and plays it while the backend scans in the background.
- **Via CLI** — OpenCV reads the file directly without a running server (useful for headless testing).

**Run:**

```powershell
cd backend
.\venv\Scripts\activate
python -m drone_conn.detection --video "C:\path\to\your\video.mp4" --block_id test_block --user_id test_user
```

**Optional — process every Nth frame to reduce CPU load:**

```powershell
python -m drone_conn.detection --video "C:\path\to\your\video.mp4" `
  --block_id test_block --user_id test_user --frame_skip 3
```

`--frame_skip 3` means process frame 1, 4, 7, … (3× faster, slightly lower accuracy on fast-moving objects).

**Expected output:**

```
🎬 MP4 scan mode
   Video      : C:\path\to\your\video.mp4
   Block ID   : test_block
   User ID    : test_user
   Frame skip : 1

🎬 Opening video: C:\path\to\your\video.mp4
   Total frames : 2400
   Source FPS   : 25.0
   Frame skip   : 1 (processing every 1 frame(s))
   Scan ID      : <auto-generated>

Frame 1/2400 processed — Total=0 (B:0, NB:0, NV:0)
Frame 2/2400 processed — Total=2 (B:2, NB:0, NV:0) [+2 new]
...
✅ Video scan complete — 2400 frames read, 2400 frames processed
📊 Final Results:
   Total Pineapples : 142
   Bearing          : 105 (73.9%)
   Non-Bearing      : 28 (19.7%)
   Non-Viable       : 9 (6.3%)
🔔 Checking alert thresholds...
```

> Press `Ctrl+C` at any time to stop early — partial results are still saved to Firestore.

---

### Option C — Static video file via Python HTTP server

Use a pre-recorded video converted to HLS. Detection stops automatically after the video ends.

> **Port note:** Use port **8080**, not 8888. MediaMTX occupies 8888 — running both on the same port crashes MediaMTX.

**Step 1 — Convert video to HLS:**

```powershell
mkdir output
ffmpeg -i "C:\path\to\your\video.mp4" -c copy -start_number 0 `
  -hls_time 10 -hls_list_size 0 `
  -hls_segment_filename "output\index%d.ts" -f hls output\index.m3u8
```

> Use `-c copy`, not `-codec: copy` (the space causes FFmpeg to fail silently).

**Step 2 — Serve the HLS files on port 8080:**

```powershell
cd output
python -m http.server 8080
```

**Step 3 — Start the Flask backend (separate terminal):**

```powershell
cd backend
.\venv\Scripts\activate
python app.py
```

**Step 4 — Trigger detection:**

```powershell
Invoke-RestMethod -Uri "http://localhost:5000/api/drone/start-detection" `
  -Method POST `
  -ContentType "application/json" `
  -Body '{"hls_url":"http://localhost:8080/index.m3u8","block_id":"test_block_id","user_id":"test_user","fps":1}'
```

**Or run detection.py directly (HLS mode):**

```powershell
cd backend
.\venv\Scripts\activate
python -m drone_conn.detection http://localhost:8080/index.m3u8 test_block test_user
```

**Expected output:**
```
⏳ Waiting for HLS playlist to become ready...
✅ HLS playlist ready (attempt 1)
✅ HLS VideoCapture opened (attempt 1): http://localhost:8080/index.m3u8
⏳ Warming up stream (draining 10 buffered frames)...
🎥 Stream capture started - Processing at 1 FPS
📈 Capture: 71.9 FPS | frame size: 1920×1080 | queue: 0/10
📊 Frame 7: Total=4 (B:3, NB:1, NV:0) [+1 new]
📊 Frame 11: Total=8 (B:4, NB:4, NV:0) [+4 new]
🛑 Stream ended after 5 reconnect(s) (static file finished) — stopping capture
```

> Once the video ends, the system reconnects up to 5 times then stops cleanly. This is expected — a live drone stream never hits EOF so it runs until you click "End Scan".

---

## API Endpoints Reference

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/test` | Health check |
| POST | `/api/drone/prepare` | Auto-start MediaMTX, return RTMP URL |
| POST | `/api/drone/connect` | Validate RTMP URL and return HLS URL |
| GET | `/api/drone/status?path=NAME` | Check stream health |
| POST | `/api/drone/start-detection` | Start YOLO+DeepSORT detection on live HLS stream |
| POST | `/api/drone/stop-detection` | Stop detection, finalize scan |
| POST | `/api/drone/upload-video` | Upload MP4, start async background scan, return `scan_id` |

**`/api/drone/upload-video` — form fields:**

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `file` | MP4 file | Yes | — | The video file to scan |
| `block_id` | string | Yes | — | Firestore block document ID |
| `user_id` | string | Yes | — | UID of the scan owner |
| `frame_skip` | int | No | `2` | Process every Nth frame (higher = faster, lower accuracy) |

**Response:** `{"ok": true, "scan_id": "<id>"}` — processing continues in background; Firestore is updated every 2 seconds.

---

## Troubleshooting

### Issue 1: "ModuleNotFoundError: No module named 'torch'"

Make sure the virtual environment is activated:

```bash
cd backend
.\venv\Scripts\activate
pip install -r requirements.txt
```

---

### Issue 2: "Firebase service account not found"

Check the file is in the right place:

```bash
dir backend\serviceAccountKey.json
```

---

### Issue 3: MediaMTX fails to start

Check that `mediamtx.exe` exists at `pinevision\mediamtx\mediamtx.exe`:

```bash
dir mediamtx\mediamtx.exe
```

If the file is missing, re-download MediaMTX and extract to the `mediamtx\` folder.

You can also start it manually for debugging:
```bash
cd mediamtx
.\mediamtx.exe
```

The control API should be reachable at `http://localhost:9997/v3/paths/list`.

---

### Issue 4: MediaMTX fails with "bind: Only one usage of each socket address" on port 8888

Another process (often a leftover `python -m http.server 8888`) is holding the port.

Find and kill it:
```powershell
netstat -ano | findstr ":8888"
# Note the PID in the last column, then:
Stop-Process -Id <PID> -Force
```

Then restart MediaMTX. For static file testing, always use port **8080** instead of 8888.

---

### Issue 5: "HTTP 404 — no publisher streaming to this path yet"

MediaMTX is running but nothing is publishing to `pinevision_scan`. Detection waits up to 20 seconds then gives up.

Fix: start a stream source before triggering detection — either the DJI drone or the FFmpeg test stream (see **Testing Without Drone → Option A**).

---

### Issue 6: "Failed to open HLS stream"

Verify MediaMTX is running and the stream path is correct. Test in browser:
```
http://localhost:8888/pinevision_scan/index.m3u8
```

---

### Issue 7: "FFmpeg not found"

Install FFmpeg and add to PATH:
```bash
ffmpeg -version
```

---

### Issue 8: Detection runs but doesn't update Firebase

Test Firebase connection:
```bash
cd backend
.\venv\Scripts\activate
python -c "import firebase_admin; from firebase_admin import credentials, firestore; cred = credentials.Certificate('serviceAccountKey.json'); firebase_admin.initialize_app(cred); print('Connected!')"
```

Also check:
- Internet connection is active
- `serviceAccountKey.json` credentials are valid and not expired
- Firestore security rules allow writes to `blocks`, `scans`, and `monitoring_alerts`
- The composite index on `monitoring_alerts` is built (see Step 6)

---

### Issue 9: "Port 5000 already in use"

```bash
# Find what's using port 5000:
netstat -ano | findstr :5000

# Kill the process:
taskkill /PID <process_id> /F

# Or change Flask port in app.py:
# app.run(host='0.0.0.0', port=5001, debug=True)
```

---

### Issue 10: Alerts not being created after scan

Ensure the Firestore composite index on `monitoring_alerts` is active (see Step 6).
Without it, the query in `check_thresholds_and_create_alerts()` will throw an error.

---

## Project Structure

```
pinevision/
├── .gitignore
├── backend/
│   ├── drone_conn/
│   │   ├── detection.py          # YOLO + DeepSORT — live HLS, async MP4 upload, CLI MP4 modes
│   │   ├── firebase_client.py    # Firestore batch writes + scan lifecycle
│   │   ├── stream_capture.py     # Frame capture — prefers RTSP over HLS for MediaMTX streams
│   │   ├── routes.py             # API endpoints (/api/drone/*) incl. /upload-video
│   │   ├── service.py            # Stream connection service
│   │   ├── mediamtx.py           # MediaMTX client (stream path queries)
│   │   ├── process_manager.py    # Auto-start/stop MediaMTX process
│   │   └── network.py            # Local IPv4 detection
│   ├── requirements.txt
│   ├── serviceAccountKey.json    # Firebase credentials (NOT in Git)
│   ├── best.pt                   # YOLO model (NOT in Git)
│   ├── app.py                    # Flask server (serves frontend + API)
│   ├── test_imports.py
│   └── venv/                     # Virtual environment (NOT in Git)
│
├── frontend/
│   ├── pages/client/
│   │   ├── drone-view.html       # Live detection UI
│   │   ├── blocks.html           # Blocks list
│   │   └── blocks-view.html      # Block details
│   └── js/
│       ├── drone-view.js         # Detection frontend logic
│       ├── app.js                # SPA navigation
│       ├── scans.js              # Scan history
│       ├── auth.js               # Firebase auth
│       ├── data.js               # Data management
│       └── utils.js              # Utilities
│
├── mediamtx/
│   ├── mediamtx.exe              # RTMP to HLS converter (auto-started)
│   └── mediamtx.yml              # MediaMTX configuration
│
├── SETUP_INSTRUCTIONS.md
└── FIXES_NEEDED.md               # Known issues and pending fixes
```

---

## Quick Start Checklist

- [ ] Python 3.11+ installed
- [ ] Repository cloned
- [ ] Virtual environment created and activated
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] `serviceAccountKey.json` in `backend/`
- [ ] Firestore composite index created on `monitoring_alerts` (blockId ASC, resolved ASC)
- [ ] YOLO model (`best.pt`) in `backend/`
- [ ] FFmpeg installed and on PATH
- [ ] MediaMTX extracted to `mediamtx\mediamtx.exe`
- [ ] Test imports pass (`python test_imports.py`)
- [ ] Backend server starts (`python app.py`) and shows Firebase connected
- [ ] Frontend loads at `http://localhost:5000`

---

## Support

**For issues or questions:**
- Check `FIXES_NEEDED.md` for known issues and pending fixes
- Review Firebase Console logs: https://console.firebase.google.com/
- Check Python terminal logs for detailed error messages
- Contact team lead for Firebase credentials or model files

---

**Last Updated:** May 2026
**Version:** 1.4
