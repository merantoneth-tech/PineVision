# PineVision - Setup Instructions

Complete guide to set up and run the real-time pineapple detection system.

---

## 📋 Prerequisites

### Software Requirements:
- ✅ **Python 3.11+** (you have Python 3.13 ✅)
- ✅ **Git** (for version control)
- ✅ **FFmpeg** (for video processing)
- ✅ **MediaMTX** (for RTMP to HLS conversion)

### Hardware Requirements:
- Computer with at least 8GB RAM (16GB recommended)
- DJI Drone with RTMP streaming capability
- Stable internet connection
- GPU optional but recommended for faster processing

---

## 🚀 Installation Steps

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
(venv) C:\pinevision\backend>

---

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

**Expected time:** 5-10 minutes (PyTorch is large ~200MB)

**Packages installed:**
- PyTorch 2.12.0+cpu
- OpenCV 4.13.0
- Ultralytics (YOLOv5)
- DeepSORT Realtime
- Firebase Admin SDK
- Flask

---

### 4. Verify Installation

```bash
python test_imports.py
```

**Expected output:**
✅ PyTorch: 2.12.0+cpu
✅ OpenCV: 4.13.0
✅ Firebase Admin SDK installed
✅ DeepSORT installed
🎉 All core dependencies installed successfully!

---

### 5. Set Up Firebase Credentials

**You need 2 Firebase credential files:**

#### **File 1: `firebase-service-account.json`**

**Download from Firebase Console:**
1. Go to: https://console.firebase.google.com/
2. Select project: **pinevision-632aa**
3. Click: ⚙️ **Project settings** → **Service accounts** tab
4. Click: **"Generate new private key"**
5. Rename downloaded file to: `firebase-service-account.json`
6. Place in: `backend/firebase-service-account.json`

#### **File 2: `serviceAccountKey.json`**

**Get from team lead** (or download if you're the admin)
- Place in: `backend/serviceAccountKey.json`

---

### 6. Verify Firebase Connection

```bash
python -c "from drone_conn.firebase_client import initialize_firebase; initialize_firebase(); print('✅ Firebase connected!')"
```

**Expected output:**
✅ Firebase initialized successfully
✅ Firebase connected!

---

### 7. Add YOLO Model

**Get `best.pt` from team lead** (or use your trained model)
- Place in: `backend/best.pt`
- File size: ~100MB
- Model classes: bearing, non-bearing, non-viable

**Verify model loads:**
```bash
python -c "import torch; model = torch.hub.load('ultralytics/yolov5', 'custom', path='best.pt'); print('✅ YOLO model loaded!')"
```

---

### 8. Install FFmpeg

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

### 9. Install MediaMTX

**Download from:** https://github.com/bluenviron/mediamtx/releases

1. Download `mediamtx_v1.x.x_windows_amd64.zip`
2. Extract to: `C:\pinevision\mediamtx\`
3. Run: `mediamtx.exe` (keep it running)

---

## 🎥 Running the System

### Option 1: With Live Drone Stream (Full System)

**Step 1 - Start MediaMTX:**
```bash
cd mediamtx
.\mediamtx.exe
```

**Keep this terminal open!**

---

**Step 2 - Start Backend Server:**

Open a NEW terminal:
```bash
cd backend
.\venv\Scripts\activate
python app.py
```

**Expected output:**
Running on http://127.0.0.1:5000
Debug mode: on

**Keep this terminal open!**

---

**Step 3 - Open Frontend:**

Open in browser: file:///C:/pinevision/frontend/pages/client/drone-view.html?blockId=YOUR_BLOCK_ID

Replace `YOUR_BLOCK_ID` with actual block ID from Firebase.

---

**Step 4 - Connect Drone:**

1. Start your DJI drone
2. Enable RTMP streaming in DJI Fly app
3. Get RTMP URL (example: `rtmp://192.168.1.100:1935/live/stream`)
4. Click **"Connect Drone"** in the web interface
5. Enter RTMP URL
6. Click **"Connect"**

---

**Step 5 - Start Detection:**

Detection starts automatically when stream connects!

Watch the stats panel update in real-time:
- **Bearing %** - Pineapples with fruit
- **Non-Bearing %** - Pineapples without fruit
- **Non-Viable %** - Discolored/diseased pineapples
- **Total Count** - Total pineapples detected

---

**Step 6 - End Scan:**

Click **"End Scan"** when finished. Data is saved to Firebase automatically!

---

## 🧪 Testing Without Drone

### Option 2: Test with Video File

**Step 1 - Convert video to HLS:**

```bash
ffmpeg -i "C:\path\to\your\video.mp4" -codec: copy -start_number 0 -hls_time 10 -hls_list_size 0 -f hls output\index.m3u8
```

---

**Step 2 - Serve HLS stream:**

Open a NEW terminal:
```bash
cd output
python -m http.server 8888
```

---

**Step 3 - Run detection:**

Open another NEW terminal:
```bash
cd backend
.\venv\Scripts\activate
python -m drone_conn.detection http://localhost:8888/index.m3u8 test_block test_user
```

**Expected output:**
📦 Loading YOLO model from best.pt...
✅ YOLO model loaded successfully
🔄 Initializing DeepSORT tracker...
✅ DeepSORT tracker initialized
🎥 Stream capture started - Processing at 1 FPS
📊 Frame 1: Total=5 (B:3, NB:2, NV:0) [+5 new]
📊 Frame 2: Total=12 (B:8, NB:3, NV:1) [+7 new]
📊 Frame 3: Total=18 (B:12, NB:4, NV:2) [+6 new]

---

## 🔧 Troubleshooting

### Issue 1: "ModuleNotFoundError: No module named 'torch'"

**Solution:** Make sure virtual environment is activated

```bash
cd backend
.\venv\Scripts\activate
pip install -r requirements.txt
```

---

### Issue 2: "Firebase service account not found"

**Solution:** Check file location

```bash
# File should exist at:
backend/firebase-service-account.json

# Check if file exists:
dir backend\firebase-service-account.json
```

---

### Issue 3: "Failed to open HLS stream"

**Solution:** Verify MediaMTX is running and stream URL is correct

```bash
# Check MediaMTX is running:
# You should see MediaMTX console output

# Test stream in browser:
http://localhost:8888/YOUR_STREAM_NAME/index.m3u8
```

---

### Issue 4: "FFmpeg not found"

**Solution:** Install FFmpeg and add to PATH

```bash
# Verify FFmpeg is installed:
ffmpeg -version

# Should show version info
```

---

### Issue 5: Detection runs but doesn't update Firebase

**Solution:** Check Firebase credentials and network

```bash
# Test Firebase connection:
python -c "from drone_conn.firebase_client import initialize_firebase; initialize_firebase(); print('Connected!')"
```

**Also check:**
- Internet connection is active
- Firebase credentials are valid
- Firestore security rules allow writes

---

### Issue 6: "Port 5000 already in use"

**Solution:** Another app is using port 5000

```bash
# Find what's using port 5000:
netstat -ano | findstr :5000

# Kill the process:
taskkill /PID <process_id> /F

# Or change Flask port in app.py:
# app.run(debug=True, port=5001)
```

---

## 📁 Project Structure
pinevision/
├── .gitignore                          # Git ignore rules
├── backend/
│   ├── drone_conn/
│   │   ├── detection.py                # YOLO + DeepSORT detection
│   │   ├── firebase_client.py          # Firebase integration
│   │   ├── stream_capture.py           # HLS frame capture
│   │   ├── routes.py                   # API endpoints
│   │   ├── service.py                  # Stream connection service
│   │   └── mediamtx.py                 # MediaMTX client
│   ├── requirements.txt                # Python dependencies
│   ├── firebase-service-account.json   # Firebase credentials (NOT in Git)
│   ├── serviceAccountKey.json          # Firebase auth (NOT in Git)
│   ├── best.pt                         # YOLO model (NOT in Git)
│   ├── app.py                          # Flask server
│   ├── test_imports.py                 # Dependency checker
│   └── venv/                           # Virtual environment (NOT in Git)
│
├── frontend/
│   ├── pages/client/
│   │   ├── drone-view.html             # Live detection UI
│   │   ├── blocks.html                 # Blocks list
│   │   └── blocks-view.html            # Block details
│   └── js/
│       ├── drone-view.js               # Detection frontend logic
│       ├── auth.js                     # Firebase auth
│       ├── data.js                     # Data management
│       └── utils.js                    # Utilities
│
├── mediamtx/
│   └── mediamtx.exe                    # RTMP to HLS converter
│
├── SETUP_INSTRUCTIONS.md               # This file
└── INTEGRATION_GUIDE.md                # Technical documentation

---

## 🎯 Quick Start Checklist

- [ ] Python 3.11+ installed
- [ ] Git cloned repository
- [ ] Virtual environment created
- [ ] Dependencies installed (`pip install -r requirements.txt`)
- [ ] Firebase credentials in place
- [ ] YOLO model (`best.pt`) in place
- [ ] FFmpeg installed
- [ ] MediaMTX downloaded
- [ ] Test imports pass (`python test_imports.py`)
- [ ] Backend server starts (`python app.py`)
- [ ] Frontend loads in browser

---

## 📞 Support

**For issues or questions:**
- Check `INTEGRATION_GUIDE.md` for technical details
- Review Firebase Console logs: https://console.firebase.google.com/
- Check Python logs in terminal for detailed error messages
- Contact team lead for Firebase credentials or model files

---

## 🎉 You're Ready!

Once all checklist items are complete, you can:
1. Connect your drone
2. Start live detection
3. View results in real-time
4. Save scan data to Firebase

**Happy scanning!** 🍍🚁

---

**Last Updated:** May 2026
**Version:** 1.0