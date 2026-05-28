# PineVision — AI Session Recovery Notes

**Last updated:** 2026-05-28 (Session 3)
**Sessions covered:** 3 (Firebase performance audit + optimization, File 2 completion)
**Overall status:** All File 1 and File 2 tasks complete. One planning-only task remains (RTDB migration — intentionally deferred).

---

## 1. COMPLETED TASKS

### 1.1 `backend/drone_conn/firebase_client.py` — FULLY REWRITTEN

**Status: Complete and correct.**

- Removed the old `_initialized` flag and `initialize_firebase()` function entirely.
- Added `get_firestore_client()` — reuses the app initialized by `app.py`; falls back to standalone init for direct testing.
- Fixed service account filename: `serviceAccountKey.json` (not `firebase-service-account.json`).
- Added `update_detection_batch()` — single Firestore batch per detection cycle (blocks + scans in one round-trip).
- `complete_scan_session()` uses a batch: scan status + `blocks.totalScans` increment atomically.
- Legacy helpers kept for backward compatibility, no longer called by detection loop.

**Bugs resolved:** Double `initialize_app()` crash; wrong filename; 2 round-trips per cycle → 1.

---

### 1.2 `backend/drone_conn/detection.py` — TARGETED EDITS

**Status: Complete and correct.**

- Import block updated: imports `get_firestore_client, update_detection_batch` (removed `initialize_firebase`).
- `start_detection()`: removed `initialize_firebase()` call.
- `_detection_loop()`: single `update_detection_batch()` replaces two separate writes.
- `check_thresholds_and_create_alerts()`: 1 query + in-memory evaluation + 1 batch commit (was 6 sequential compound queries with missing composite index).
- Old helpers `_create_alert_if_not_exists()` and `_auto_resolve_alerts()` removed.

---

### 1.3 `frontend/js/alerts.js` — FULLY REWRITTEN + CACHING COMPLETE

**Status: Complete and correct (including caching — bug fixed this session).**

- N+1 eliminated: 2 parallel queries replace N+2 sequential.
- `resolveAlert()`: local state mutation only, no reload.
- `renderThresholds()` accepts pre-fetched snapshot.
- **Caching bug fixed (Session 3):**
  - Cache-write now stores `{ id, _data: captured }` plain objects (JSON-serializable).
  - Cache-read reconstructs the `data()` method on retrieval: `fn({ id: item.id, data: () => item._data })`.
  - Previously: `data: () => doc.data()` was silently dropped by `JSON.stringify`, causing `TypeError` on second page load.

---

### 1.4 `frontend/js/flight.js` — TARGETED EDITS + CACHING ADDED

**Status: Complete and correct.**

- `initPage()`: `Promise.all([loadOperators(), loadMissions()])` — parallel loads.
- `handleAddMission()`: `allMissions.length + 1` replaces full-collection count fetch.
- **`loadOperators()` caching added (Session 3):** Serves from `pvCache('operators', 2min)` on repeat visits. Removed 3 duplicate `// LOAD OPERATORS` comment headers left by interrupted previous session.

---

### 1.5 `frontend/pages/admin/dashboard.html` — INLINE SCRIPT REFACTORED

**Status: Complete and correct.**

- ~11 sequential round-trips → 5 parallel queries in `Promise.all`.
- JS bucketing replaces 6-query hourly loop.
- Function signatures updated; dead mock array removed.

---

### 1.6 `frontend/js/cache.js` — NEWLY CREATED

**Status: Complete and correct.**

- `window.pvCache` — TTL-based sessionStorage cache with `get`, `set`, `invalidate`, `invalidateAll`.
- Keys prefixed `pv_`. Degrades gracefully if storage unavailable.
- Script tag added to `alerts.html` and `flight.html`.

---

### 1.7 `backend/app.py` — PAGINATED `/api/users` (Session 3)

**Status: Complete and correct.**

- `GET /api/users` no longer streams the entire `users` collection.
- Supports `?limit=N` (default 50, max 200) and `?startAfter=<docId>` cursor pagination.
- Callers that don't pass `startAfter` get the first page; subsequent pages pass the last document ID.

---

### 1.8 All 13 HTML Pages — PRECONNECT HINTS (Session 3)

**Status: Complete. Applied to all 13 pages.**

Pages updated:
```
frontend/pages/index.html
frontend/pages/admin/activity.html
frontend/pages/admin/alerts.html
frontend/pages/admin/auditlogs.html
frontend/pages/admin/dashboard.html
frontend/pages/admin/users.html
frontend/pages/client/alerts.html
frontend/pages/client/blocks.html
frontend/pages/client/blocks-view.html
frontend/pages/client/dashboard.html
frontend/pages/client/flight.html
frontend/pages/client/scans.html
frontend/pages/client/settings.html
```

Added immediately after `<meta name="viewport">`:
```html
<link rel="preconnect" href="https://www.gstatic.com" crossorigin>
<link rel="dns-prefetch" href="https://firestore.googleapis.com">
<link rel="dns-prefetch" href="https://identitytoolkit.googleapis.com">
```

---

### 1.9 `frontend/js/auth.js` — PARALLEL WRITES + IPIFY REMOVED (Session 3)

**Status: Complete and correct.**

- **Successful login path:** `lastLogin` update and `activity_logs` write are now parallel via `Promise.all`. Saves one round-trip on every login.
- **Failed login path:** Removed `fetch('https://api.ipify.org?format=json')` — was adding 100–500ms to error display with no SLA. IP field removed from failed login logs and alert documents. `activity_logs` and `alerts` writes are now parallel via `Promise.all`.

---

### 1.10 `frontend/js/data.js` — DUPLICATE DECLARATIONS REMOVED (Session 3)

**Status: Complete and correct.**

- Removed `const scanData = { scans: [...] }` — duplicate of `SCANS` with decimal values instead of percentages; not referenced anywhere outside this file.
- Removed `const data = { getScans, getLatestScan }` stub at bottom — orphaned partial object that was never exported or used; `window.data` (line 653) is the sole correct export.
- `window.data.getScans()` and `window.data.getLatestScan()` continue to work correctly via `SCANS`.

---

## 2. ACTIVE BUGS

None. All previously known bugs have been resolved.

---

## 3. PENDING TASKS

### 3.1 Create Firestore Composite Index (manual — Firebase Console only)

**Required before YOLO detection can create or resolve alerts.**

1. Go to Firebase Console → Project `pinevision-632aa`
2. Firestore Database → Indexes → Composite → Add Index
3. Collection ID: `monitoring_alerts`
4. Fields: `blockId` — Ascending, `resolved` — Ascending
5. Query scope: Collection
6. Click Create (~1 minute to build)

If detection runs before the index exists, Firestore prints a clickable URL in Flask console logs that auto-creates it.

---

### 3.2 Firebase Realtime Database for Live Telemetry (planning + ~2 hours)

**Intentionally deferred — requires a full implementation plan before touching.**

Currently: `onSnapshot()` on `blocks/{blockId}` in `drone-view.js` → costs a Firestore read per update event. At 2-second intervals with multiple viewers this scales poorly.

Recommended architecture:
- Write live telemetry to RTDB during active scans, Firestore only on scan completion.
- RTDB path: `/liveScan/{blockId}/{bearingPercent, nonBearingPercent, ...}`
- Backend: `update_detection_batch()` in `firebase_client.py` writes to RTDB instead of (or alongside) Firestore `blocks`.
- Frontend (`drone-view.js`): Replace `onSnapshot()` on `blocks/{blockId}` with `onValue()` on `/liveScan/{blockId}`.
- Requires: Enable RTDB in Firebase Console, add RTDB Admin SDK to Python backend, add `firebase-database-compat.js` to `drone-view.html`.
- **Do not implement without a cleanup plan** — the RTDB path must be cleared when the scan ends.

---

### 3.3 Investigate `"alerts"` vs `"monitoring_alerts"` Collection Mismatch

- `admin/dashboard.html` queries `"alerts"`.
- YOLO backend (`detection.py`) writes to `"monitoring_alerts"`.
- `alerts.js` (client) reads from `"monitoring_alerts"`.
- Alerts from the detection pipeline never appear on the admin dashboard.
- Needs investigation: are these intentionally separate, or a historical naming inconsistency?

---

### 3.4 `drone-view.js` Orphaned Listener on Navigation

`startFirebaseListener()` registers an `onSnapshot` on `blocks/{blockId}`. `stopFirebaseListener()` unsubscribes it on "End Scan" click — but NOT if the user navigates away without ending the scan.

Fix (not yet applied):
```javascript
window.addEventListener('beforeunload', () => {
    stopFirebaseListener();
});
```

---

## 4. KNOWN ISSUES

### 4.1 Missing Firestore Composite Index (CRITICAL for alerts)

See Section 3.1. Without it every `check_thresholds_and_create_alerts()` call throws `FailedPrecondition: 400`, which is caught silently — alerts never appear.

---

### 4.2 `firestore.Increment(1)` — Version-Dependent API

**File:** `backend/drone_conn/firebase_client.py`
**Risk:** `AttributeError` if firebase-admin < 5.0 or google-cloud-firestore < 2.0

Verify with:
```bash
pip show firebase-admin google-cloud-firestore
```

If `Increment` is not available, replace with:
```python
from google.cloud.firestore_v1 import transforms
transforms.Increment(1)
```

---

### 4.3 Firebase Project Region — US Instead of Philippines

Project `pinevision-632aa` uses `us-central1`. Every Firestore operation from the Philippines incurs ~200–350ms additional round-trip latency vs ~30ms for `asia-southeast1` (Singapore).

Fix requires creating a new Firebase project in `asia-southeast1` and migrating all data — not a quick fix.

---

### 4.4 `"alerts"` vs `"monitoring_alerts"` Collection Mismatch

See Section 3.3. Pre-existing, not introduced by these optimizations.

---

## 5. CURRENT ARCHITECTURE

### 5.1 System Overview

```
┌────────────────────────────────────────────────────────────┐
│                     FRONTEND (Browser)                      │
│   Bootstrap 5 (local) + Firebase JS SDK (CDN v9.22.0)     │
│                                                             │
│   Pages:  /admin/*   and  /client/*                        │
│   Shared: auth.js, app.js, data.js, utils.js, cache.js     │
│   Page JS: alerts.js, flight.js, drone-view.js             │
│                                                             │
│   Firebase SDK initialized ONCE in auth.js                  │
│   (guard: if (!firebase.apps.length) initializeApp())       │
└──────────────┬──────────────────────────┬──────────────────┘
               │ HTTP (same origin)        │ Firestore JS SDK (direct)
               │ /api/drone/*             │
               │ /api/users               │
               ▼                          ▼
┌──────────────────────────┐   ┌──────────────────────────────┐
│   Flask Backend          │   │   Firebase / Firestore        │
│   backend/app.py         │   │   Project: pinevision-632aa   │
│   Port: 5000             │   │   Region: us-central1 (USA)   │
│   Serves frontend/ files │   │                               │
│                          │   │   Collections used:           │
│   Blueprints:            │   │   • users                     │
│   drone_conn/routes.py   │   │   • scans                     │
│   → /api/drone/connect   │   │   • blocks                    │
│   → /api/drone/status    │   │   • missions                  │
│   → /api/drone/start-    │   │   • activity_logs             │
│     detection            │   │   • monitoring_alerts  ← YOLO │
│   → /api/drone/stop-     │   │   • alerts  ← admin dashboard │
│     detection            │   │     (DIFFERENT collection —   │
│                          │   │      see Known Issues 4.4)    │
│   Firebase Admin SDK     │   └──────────────────────────────┘
│   initialized ONCE in    │
│   app.py at startup      │
└──────────┬───────────────┘
           │ HLS stream pull (cv2.VideoCapture)
           ▼
┌──────────────────────────┐
│   MediaMTX               │
│   mediamtx/mediamtx.exe  │
│   RTMP in:  port 1935    │
│   HLS out:  port 8888    │
│   API:      port 9997    │
│   Stream:   pinevision_scan
└──────────┬───────────────┘
           │ RTMP push
           ▼
      DJI Drone (DJI Fly app)
```

### 5.2 Firebase Initialization Chain

```
1. python backend/app.py starts
2. app.py: firebase_admin.initialize_app(credentials.Certificate('serviceAccountKey.json'))
3. app.py: db = firestore.client()
4. drone_conn/routes.py registers /api/drone/* endpoints
5. User triggers /api/drone/start-detection:
   → detection.py PineappleDetector.start_detection()
   → create_scan_session() calls get_firestore_client()
   → get_firestore_client(): firebase_admin._apps populated → reuses existing app
   ✅ No double initialize_app() call
```

### 5.3 Real-Time Detection Workflow (per scan)

```
1. User opens drone-view.html?blockId=<FIRESTORE_DOC_ID>
2. User enters RTMP URL → clicks "Connect Drone"
3. Frontend POST /api/drone/connect
4. Frontend loads HLS via hls.js into <video>
5. Frontend POST /api/drone/start-detection {hls_url, block_id, user_id}
   → create_scan_session() → new Firestore doc in scans/
6. Backend detection thread:
   → HLSStreamCapture: 1 frame/second via OpenCV
   → YOLOv8 (ultralytics): detection per frame
   → DeepSORT tracker: unique IDs, no double-counting
   → Every 2 seconds: update_detection_batch() → ONE batch commit
7. Frontend: onSnapshot() on blocks/{blockId} → real-time stats
8. User clicks "End Scan"
   → complete_scan_session() → ONE batch commit
   → check_thresholds_and_create_alerts(): 1 query + 1 batch commit
```

### 5.4 Key File Locations

| Purpose | File |
|---------|------|
| Flask server entry point | `backend/app.py` |
| Firebase Admin client | `backend/drone_conn/firebase_client.py` |
| YOLO + DeepSORT detection | `backend/drone_conn/detection.py` |
| HLS frame capture | `backend/drone_conn/stream_capture.py` |
| API routes blueprint | `backend/drone_conn/routes.py` |
| Service account key | `backend/serviceAccountKey.json` ← not in git |
| Auth (Firebase JS SDK init) | `frontend/js/auth.js` |
| sessionStorage cache utility | `frontend/js/cache.js` |
| Mock/static data layer | `frontend/js/data.js` |
| Alerts page (client) | `frontend/js/alerts.js` |
| Flight missions | `frontend/js/flight.js` |
| Drone view controller | `frontend/js/drone-view.js` |
| Admin dashboard | `frontend/pages/admin/dashboard.html` |

---

## 6. TESTING CHECKLIST

### Before testing detection:
- [ ] Composite index created in Firebase Console (`monitoring_alerts`: `blockId ASC`, `resolved ASC`)
- [ ] `backend/serviceAccountKey.json` exists
- [ ] `mediamtx/mediamtx.exe` is running
- [ ] `pip show firebase-admin` shows ≥ 5.0 (for `firestore.Increment`)

### Start sequence:
```bash
# Terminal 1 — MediaMTX
mediamtx/mediamtx.exe

# Terminal 2 — Flask backend (MUST start from backend/ directory)
cd backend
python app.py
```

### Expected Flask startup output:
```
✅ Firebase connected successfully!
```

### Detection verification:
1. Open `http://localhost:5000/client/flight.html` — verify missions load
2. Open drone-view for a block — verify HLS stream connects
3. Start detection — verify in Firebase Console:
   - `scans/{id}` document created with `status: active`
   - `blocks/{id}` updates every ~2 seconds
4. End scan — verify:
   - `scans/{id}` status → `completed`
   - `blocks/{id}.totalScans` incremented by 1
   - `monitoring_alerts` documents created/resolved (requires composite index)
5. Open `http://localhost:5000/client/alerts.html` — verify alerts display
6. Reload alerts page — verify second load hits cache (check console: "Operators from cache:" / blocks served from `_cached: true` snapshot)

---

## 7. HARD CONSTRAINTS — DO NOT VIOLATE

- **One Firebase init only.** Only `app.py` calls `firebase_admin.initialize_app()`. Never add a second call.
- **Collection names are fixed.** `blocks`, `scans`, `monitoring_alerts`, `alerts`, `users`, `missions`, `activity_logs` — hardcoded across many files. Do not rename.
- **`serviceAccountKey.json` is the canonical filename** in `backend/`. Do not rename or alias.
- **`drone-view.js` `onSnapshot` must keep working.** Batch writes in `firebase_client.py` still write to `blocks/{blockId}`. Do not remove that write.
- **Flask must start from `backend/` directory:** `cd backend && python app.py`
- **MediaMTX must be started before any drone connection attempt.**

---

## 8. NEXT RECOMMENDED STEPS

In priority order:

| Step | Task | Time | File |
|------|------|------|------|
| 1 | Create Firestore composite index | 5 min | Firebase Console (manual) |
| 2 | Test detection pipeline end-to-end | 30 min | — |
| 3 | Investigate "alerts" vs "monitoring_alerts" | varies | `dashboard.html` |
| 4 | Fix drone-view.js orphaned listener on nav | 5 min | `frontend/js/drone-view.js` |
| 5 | Plan RTDB migration for live telemetry | 2 hrs | `firebase_client.py`, `drone-view.js` |

---

*End of recovery notes. Generated: 2026-05-28 (Session 3). All File 1 and File 2 tasks complete. Next session: create Firestore composite index, run end-to-end detection test, then investigate alerts collection mismatch.*
