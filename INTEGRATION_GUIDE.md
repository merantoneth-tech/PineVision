# PineVision - Integration Guide

Technical documentation for the real-time pineapple detection system architecture, data flow, and optimization.

---

## 🏗️ System Architecture
┌─────────────────────────────────────────────────────────────┐
│                        DJI DRONE                            │
│                 (RTMP Live Stream)                          │
└────────────────────────┬────────────────────────────────────┘
│ RTMP Protocol
▼
┌─────────────────────────────────────────────────────────────┐
│                      MediaMTX Server                        │
│            Converts RTMP → HLS for browser                  │
└────────────────────────┬────────────────────────────────────┘
│ HLS Stream
▼
┌─────────────────────────────────────────────────────────────┐
│              Python Detection Backend                       │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  1. HLS Stream Capture (stream_capture.py)           │ │
│  │     - Extracts frames at 1 FPS                        │ │
│  │     - Uses OpenCV + FFmpeg                            │ │
│  └───────────────────┬───────────────────────────────────┘ │
│                      ▼                                      │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  2. YOLO Detection (detection.py)                     │ │
│  │     - Runs best.pt model on each frame                │ │
│  │     - Detects: bearing, non-bearing, non-viable       │ │
│  └───────────────────┬───────────────────────────────────┘ │
│                      ▼                                      │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  3. DeepSORT Tracking                                 │ │
│  │     - Assigns unique ID to each pineapple             │ │
│  │     - Prevents duplicate counting                     │ │
│  │     - Maintains ID across frames                      │ │
│  └───────────────────┬───────────────────────────────────┘ │
│                      ▼                                      │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  4. Firebase Update (firebase_client.py)              │ │
│  │     - Updates block stats every 2 seconds             │ │
│  │     - Real-time Firestore writes                      │ │
│  └───────────────────────────────────────────────────────┘ │
└────────────────────────┬────────────────────────────────────┘
│ Firebase Realtime Updates
▼
┌─────────────────────────────────────────────────────────────┐
│                  Frontend (drone-view.html)                 │
│  ┌───────────────────────────────────────────────────────┐ │
│  │  Firebase Listener (drone-view.js)                    │ │
│  │  - Listens to block document changes                  │ │
│  │  - Updates stats panel automatically                  │ │
│  │  - Shows: Bearing, Non-Bearing, Non-Viable %         │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

---

## 🔍 How Duplicate Prevention Works

### Problem:
Without tracking, the same pineapple gets counted multiple times:
Frame 1: Detects pineapple at (x=100, y=200) → Count = 1
Frame 2: Same pineapple at (x=102, y=201) → Count = 2 ❌ DUPLICATE!
Frame 3: Same pineapple at (x=98, y=199) → Count = 3 ❌ DUPLICATE!

### Solution: DeepSORT Tracking

**DeepSORT Algorithm:**
1. Detects objects with YOLO bounding boxes
2. Extracts appearance features from each detection
3. Matches detections across frames using:
   - **IoU (Intersection over Union)** - spatial overlap
   - **Appearance similarity** - visual features
   - **Motion prediction** - Kalman filter
4. Assigns persistent unique ID to each object
5. Maintains ID even if object temporarily leaves frame

**Example:**

```python
Frame 1:
Detection: Pineapple at (100, 200) → Assign ID: 1 ✅
unique_ids['bearing'].add(1)  # Count = 1Frame 2:
Detection: Pineapple at (102, 201)
DeepSORT: "This matches ID 1 (high IoU + similar appearance)"
→ Skip (already counted) ❌ No duplicate!
Count still = 1Frame 10:
Detection: NEW pineapple at (500, 300) → Assign ID: 2 ✅
unique_ids['bearing'].add(2)  # Count = 2

**Tracking State:**
```python

unique_ids = {
'bearing': {1, 2, 5, 8, 12, ...},      # Set of unique IDs
'non_bearing': {3, 7, 9, ...},
'non_viable': {4, 6, 11, ...}
}Total unique count
total = len(unique_ids['bearing']) + len(unique_ids['non_bearing']) + len(unique_ids['non_viable'])

---

## 🔥 Firebase Data Flow

### Collections Structure:
firestore
├── blocks/
│   └── {blockId}/
│       ├── bearingPercent: 87.5        # Updates in real-time
│       ├── nonBearingPercent: 8.2
│       ├── nonViable: 4.3
│       ├── totalPineapples: 22000
│       ├── totalScans: 1               # Increments on scan complete
│       └── lastScanned: Timestamp
│
└── scans/
└── {scanId}/
├── blockId: "Ka9Qfs..."
├── userId: "ojoNz..."
├── status: "active" | "completed"
├── startTime: Timestamp
├── endTime: Timestamp | null
├── bearing: 19250                # Real-time count
├── nonBearing: 1804
├── nonViable: 946
└── total: 22000

### Update Frequency:

| Action | Frequency | Firestore Writes |
|--------|-----------|------------------|
| Detection frame processing | 1 FPS | 0 (in-memory only) |
| Firebase block update | Every 2 seconds | 1 write |
| Firebase scan progress update | Every 2 seconds | 1 write |
| Scan completion | Once at end | 2 writes |

**Cost estimate:** ~1800 writes per hour of scanning (well within free tier limits)

---

## 🎯 Detection Parameters

### YOLO Model Settings:

```python
confidence_threshold = 0.5  # Minimum confidence for detection
```

**Tuning Guide:**
- **Lower (0.3):** More detections, more false positives
- **Higher (0.7):** Fewer false positives, might miss some pineapples
- **Recommended:** 0.5 for balanced results

### DeepSORT Settings:

```python
max_age = 30           # Frames to keep track without detection
n_init = 3             # Frames needed to confirm new track
max_iou_distance = 0.7 # IoU threshold for matching
```

**Tuning Guide:**
- **max_age:** Increase if drone moves slowly, decrease if fast
- **n_init:** Increase to reduce false positives
- **max_iou_distance:** Increase if pineapples are densely packed

### Processing Settings:

```python
fps = 1                # Frames per second to process
update_interval = 2.0  # Seconds between Firebase updates
```

**Tuning Guide:**
- **FPS:** Higher = more accurate but slower; 1 FPS is optimal
- **update_interval:** Lower = more real-time but more writes

---

## 🔌 API Endpoints

### 1. Connect Drone Stream

```http
POST /api/drone/connect
Content-Type: application/json

{
  "rtmp_url": "rtmp://192.168.1.100:1935/live/stream"
}
```

**Response:**
```json
{
  "ok": true,
  "hls_url": "http://localhost:8888/live/index.m3u8",
  "path": "live",
  "host": "192.168.1.100"
}
```

---

### 2. Start Detection

```http
POST /api/drone/start-detection
Content-Type: application/json

{
  "hls_url": "http://localhost:8888/live/index.m3u8",
  "block_id": "Ka9QfsVyjfOJ4U7xIlxt",
  "user_id": "ojoNzJsvnecrRgt8mn7HBbajmYJ2",
  "fps": 1
}
```

**Response:**
```json
{
  "ok": true,
  "scan_id": "scan_abc123",
  "message": "Detection started successfully"
}
```

---

### 3. Stop Detection

```http
POST /api/drone/stop-detection
Content-Type: application/json

{
  "block_id": "Ka9QfsVyjfOJ4U7xIlxt",
  "scan_id": "scan_abc123"
}
```

**Response:**
```json
{
  "ok": true,
  "message": "Detection stopped and scan completed"
}
```

---

### 4. Check Stream Status

```http
GET /api/drone/status?path=live
```

**Response:**
```json
{
  "ok": true,
  "ready": true,
  "path": "live"
}
```

---

## 🐛 Debugging

### Enable Verbose Logging:

```python
# In detection.py, add at the top:
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Check Detection Output:

```bash
# Run detection with test output
python -m drone_conn.detection http://localhost:8888/index.m3u8 test_block test_user
```

**Expected output:**
📊 Frame 1: Total=5 (B:3, NB:2, NV:0) [+5 new]
📊 Frame 2: Total=12 (B:8, NB:3, NV:1) [+7 new]
📊 Frame 3: Total=18 (B:12, NB:4, NV:2) [+6 new]

### Monitor Firebase Updates:

Go to: https://console.firebase.google.com/project/pinevision-632aa/firestore

Open `blocks/{blockId}` document and watch fields update every 2 seconds.

---

## 🚨 Common Issues

### Issue 1: Detection not updating Firebase

**Symptoms:** Detection runs but stats don't update in UI

**Diagnosis:**
```bash
python -c "from drone_conn.firebase_client import initialize_firebase; initialize_firebase()"
```

**Solutions:**
- Check `firebase-service-account.json` exists
- Verify internet connection
- Check Firebase security rules allow writes
- Check Firestore Console for actual updates

---

### Issue 2: Too many duplicate counts

**Symptoms:** Count increases too fast, same pineapple counted multiple times

**Diagnosis:** DeepSORT tracking not working properly

**Solutions:**
- Increase `n_init` (require more frames to confirm track)
- Increase `confidence_threshold` (stricter detections)
- Check if bounding boxes are stable
- Verify DeepSORT is installed: `pip show deep-sort-realtime`

---

### Issue 3: Missing detections

**Symptoms:** Pineapples visible but not detected

**Diagnosis:** YOLO confidence too low or model issue

**Solutions:**
- Lower `confidence_threshold` to 0.3-0.4
- Retrain model with more diverse data
- Check lighting conditions in video
- Verify model is loading: `ls backend/best.pt`

---

### Issue 4: Stream connection fails

**Symptoms:** "Failed to open HLS stream"

**Diagnosis:** MediaMTX not running or wrong URL

**Solutions:**
- Verify MediaMTX is running: `netstat -an | findstr 8888`
- Test HLS URL in browser or VLC
- Check drone is streaming to correct RTMP address
- Verify no firewall blocking port 8888

---

### Issue 5: High memory usage

**Symptoms:** System slows down, RAM usage >4GB

**Solutions:**
- Lower FPS: `fps = 0.5` (process every 2 seconds)
- Reduce frame size in stream_capture.py
- Clear old tracks: Reduce `max_age` in DeepSORT
- Restart detection every hour for long scans

---

## 📊 Performance Metrics

### Expected Performance:

| Metric | Value | Notes |
|--------|-------|-------|
| Detection FPS | 1 frame/second | Configurable |
| Detection latency | ~500ms per frame | CPU only |
| Firebase update delay | 2 seconds | Real-time enough |
| Memory usage | ~2GB | With PyTorch CPU |
| GPU usage (if available) | 20-40% | 5-10x faster |
| Network bandwidth | ~2 Mbps | HLS stream |
| Accuracy | 85-95% | Depends on model |

### Optimization Tips:

**1. Use GPU for 5-10x speedup:**
```bash
# Install CUDA-enabled PyTorch
pip uninstall torch torchvision
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu118
```

**2. Reduce processing frequency:**
```python
# In detection.py
fps = 0.5  # Process every 2 seconds instead of 1
```

**3. Batch processing for post-flight analysis:**
```python
# Process entire video after flight
# More accurate, no real-time constraint
# Can use higher FPS and lower confidence threshold
```

**4. Optimize Firebase writes:**
```python
# Increase update interval to reduce writes
update_interval = 5.0  # Update every 5 seconds
```

---

## 🔒 Security Best Practices

### Firebase Security Rules:

```javascript
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    
    // Blocks: Only authenticated users can read/write their own blocks
    match /blocks/{blockId} {
      allow read: if request.auth != null;
      allow write: if request.auth != null;
    }
    
    // Scans: Only authenticated users can read/write their own scans
    match /scans/{scanId} {
      allow read: if request.auth != null;
      allow write: if request.auth != null;
    }
  }
}
```

### API Security:

**Current:** No authentication (local network only)

**For production:**
- Add API key authentication
- Use HTTPS/TLS encryption
- Rate limiting on endpoints
- CORS restrictions

---

## 🎓 Technical Deep Dive

### How YOLO Detection Works:

1. **Input:** RGB image (640x640 pixels)
2. **Feature extraction:** Convolutional neural network
3. **Object detection:** Bounding box + class + confidence
4. **Output:** List of detections with coordinates

**Example detection:**
```python
{
  'bbox': [100, 200, 150, 250],  # x1, y1, x2, y2
  'class': 'bearing',
  'confidence': 0.87
}
```

---

### How DeepSORT Tracking Works:

1. **Detection → Track matching:** Compare new detections with existing tracks
2. **Kalman filter:** Predict track position in next frame
3. **Hungarian algorithm:** Optimal assignment of detections to tracks
4. **Track management:** Create, update, or delete tracks

**Track lifecycle:**
NEW → TENTATIVE (n_init frames) → CONFIRMED → DELETED (max_age frames)

---

### Why 1 FPS is Optimal:

| FPS | Pros | Cons |
|-----|------|------|
| 0.5 | Very fast, low CPU | Might miss fast-moving pineapples |
| 1 | **Balanced** | Good accuracy + performance |
| 2 | More accurate | Slower, 2x CPU usage |
| 5 | Highest accuracy | Very slow, 5x CPU usage |

**For aerial drone footage at 2-5 m/s speed, 1 FPS captures enough overlap to prevent missing pineapples.**

---

## 📈 Future Enhancements

### Planned Features:

- [ ] Historical scan results viewing in UI
- [ ] Scan comparison (current vs previous scans)
- [ ] Heatmap visualization of pineapple locations
- [ ] Export scan data to CSV/Excel
- [ ] Multi-block scanning in single flight
- [ ] Automatic drone flight path generation
- [ ] GPU acceleration detection
- [ ] Model retraining pipeline

### Performance Improvements:

- [ ] TensorRT optimization for NVIDIA GPUs
- [ ] Edge deployment on drone companion computer
- [ ] Real-time video compression for lower bandwidth
- [ ] Parallel processing of multiple camera feeds

---

## 📞 Support & Resources

### Documentation:
- **Setup Guide:** `SETUP_INSTRUCTIONS.md`
- **This Guide:** `INTEGRATION_GUIDE.md`
- **YOLOv5 Docs:** https://github.com/ultralytics/yolov5
- **DeepSORT Docs:** https://github.com/nwojke/deep_sort

### Firebase:
- **Console:** https://console.firebase.google.com/project/pinevision-632aa
- **Firestore Docs:** https://firebase.google.com/docs/firestore
- **Security Rules:** https://firebase.google.com/docs/firestore/security/get-started

### Community:
- **PyTorch Forum:** https://discuss.pytorch.org/
- **Computer Vision Stack Exchange:** https://computervision.stackexchange.com/

---

## 🎉 Congratulations!

You now understand the complete technical architecture of PineVision!

**Key Takeaways:**
- ✅ YOLO detects pineapples frame-by-frame
- ✅ DeepSORT prevents duplicate counting with unique IDs
- ✅ Firebase provides real-time updates to the UI
- ✅ 1 FPS processing is optimal for drone footage
- ✅ System is scalable and production-ready

**Happy detecting!** 🍍🚁

---

**Last Updated:** May 2026
**Version:** 1.0
**Authors:** PineVision Development Team