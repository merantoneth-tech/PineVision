# Detection Pipeline Testing Plan
## Comparing frame_skip = 1 / 2 / 3 / 5

---

## Pre-Test API Verification Notes

Before running tests, these facts were confirmed by reading the
`deep-sort-realtime 1.3.2` source directly:

| Question | Answer |
|----------|--------|
| Does `update_tracks([], frame=frame)` advance Kalman? | **Yes** — `tracker.predict()` is always called, then `tracker.update([])` marks all tracks missed. But we do NOT use this pattern — see Fix 2 below. |
| Does `tracker.tracker.predict()` advance Kalman without marking tracks missed? | **Yes** — only `predict()` is called; `update()` is skipped, so tentative tracks survive and confirmed tracks are not aged. |
| Are appearance embeddings (mobilenet ReID) active? | **Yes** — `embedder='mobilenet'` is the DeepSort default; already active in the codebase. |
| Does DeepSort assume constant frame intervals? | **Yes** — the Kalman filter has no `dt` parameter; each `predict()` call is one fixed time-step regardless of real elapsed time. |
| When does a tentative track die? | **Immediately** on the first missed `update()` call (not after max_age). Only confirmed tracks survive max_age misses. |

---

## Fixes Implemented (this batch)

| Fix | File | Change |
|-----|------|--------|
| Fix 1 | `detection.py` | `reset_tracking(frame_skip, live_fps)` re-creates DeepSort; `_init_tracker()` scales `max_age`, `n_init`, `max_iou_distance` for the detection cadence |
| Fix 2 | `detection.py` | `advance_kalman_only()` calls `self.tracker.tracker.predict()` on every skipped frame — Kalman stays in sync without aging tracks |
| Fix 3 | `detection.py` | Explicit `iou=0.45` NMS in `detect_frame()` — tighter than default 0.7, suppresses multi-box detections on one plant |
| Fix 5 | `detection.py` | `should_detect = (frame_index == 1) or ((frame_index-1) % frame_skip == 0)` — tracking starts at frame 1, not frame `frame_skip` |
| Fix 7 | `detection.py` + `stream_capture.py` | Queue-depth warnings + dropped-frame counter in capture loop |

### Tracker parameter table after Fix 1

| frame_skip | max_age | n_init | max_iou_distance | Real-time equivalent at 25 FPS |
|------------|---------|--------|-----------------|-------------------------------|
| 1 | 30 | 3 | 0.70 | track dies after 1.2 s missed |
| 2 | 15 | 3 | 0.72 | track dies after 1.2 s missed |
| 3 | 10 | 2 | 0.75 | track dies after 1.2 s missed |
| ≥5 | 6 | 2 | 0.80 | track dies after 1.2 s missed |
| live fps=1 | 10 | 2 | 0.85 | track dies after 10 s missed |

---

## Test Setup

### Requirements

- Same MP4 video file used across all four runs
- All runs on the **same machine** (same hardware = same timing)
- Use the **synchronous** `run_video_scan()` path (CLI mode) so output is
  sequential and easy to read; async `start_video_scan()` would interleave logs
- Firebase writes during the test are fine but do not affect counts

### Command template

```bash
cd e:\PineVision\pinevision
python -m backend.drone_conn.detection \
    --video path\to\test_video.mp4 \
    --block_id TEST_BLOCK_ID \
    --user_id  TEST_USER_ID \
    --frame_skip N
```

Run once for `N = 1`, `2`, `3`, `5`.  Capture full stdout each time.

---

## Metrics to Record Per Run

Copy these values from the diagnostics summary printed at the end of each run:

```
📈 [sync scan diagnostics]
   frame_skip           :
   Frames read          :
   Frames detected      :
   Frames Kalman-only   :
   Total new det. added :
   YOLO   ms mean/max   :
   Tracker ms mean/max  :
   Wall time            :
```

Also record from the Firebase-committed final result:
```
   Bearing   count + %
   Non-bearing count + %
   Non-viable  count + %
   Total count
```

And from the per-frame log lines, note:
- Maximum `Conf=` (confirmed tracks) seen in any single frame
- Maximum `Tent=` (tentative tracks) seen in any single frame
- Highest `RawDets=` (boxes after NMS before tracker)

---

## Expected Results After Fixes

| Metric | Before fixes | After fixes (expected) |
|--------|-------------|----------------------|
| Total count at skip=1 vs skip=5 | May differ by 30–60% | Should be within 10–15% |
| Confirmed tracks peak | Varies | More consistent |
| YOLO ms | Unchanged | Unchanged |
| Tracker ms at skip=5 | Higher (more IoU failures) | Lower (Kalman predicts better) |
| Dropped frames (live) | Hidden | Now logged with count |

---

## Comparison Table (fill in after runs)

| Metric | skip=1 | skip=2 | skip=3 | skip=5 |
|--------|--------|--------|--------|--------|
| Total pineapples counted | | | | |
| Bearing count | | | | |
| Non-bearing count | | | | |
| Non-viable count | | | | |
| Frames detected | | | | |
| Frames Kalman-only | | | | |
| YOLO ms (mean) | | | | |
| Tracker ms (mean) | | | | |
| Wall time (s) | | | | |
| Det/s throughput | | | | |
| Max confirmed tracks/frame | | | | |
| Max tentative tracks/frame | | | | |

---

## Pass/Fail Criteria

### Counting Consistency ✅ Pass if:
- Total count variance across skip=1,2,3,5 is **≤ 15%** of skip=1 baseline
- Formula: `abs(count_N - count_1) / count_1 <= 0.15`

### Duplicate Rate ✅ Pass if:
- Max confirmed tracks in any single frame does not exceed expected plant density
  by more than 20% (signals double-counting has not increased)

### Missed Detection Rate ✅ Pass if:
- skip=5 total count is at least 80% of skip=1 total count

### Tracking Stability ✅ Pass if:
- `Total new det. added` (cumulative unique tracks ever seen) decreases
  predictably with higher skip (fewer frames = fewer tracks seen)
- No single skip level shows an anomalously HIGH new-detection count
  (which would indicate track-ID re-assignment / double counting)

### CPU / Speed ✅ Pass if:
- YOLO ms does not increase with frame_skip (it should be stable; skip only
  changes how often YOLO runs, not how long it takes)
- Wall-time scales approximately as `1/frame_skip` (i.e. skip=5 is ~5× faster)

### Queue Lag (live stream only) ✅ Pass if:
- Zero `⚠️ [LAG]` messages appear during a 30-second test stream at fps=1
- Dropped-frame count in capture log is 0

---

## Interpreting Results

### If skip=5 total count is LOWER than skip=1:
- Track confirmation is failing — plants visible in fewer than `n_init`
  processed frames don't get confirmed
- Try lowering `n_init` to 1 for high skip values in `_init_tracker()`

### If skip=5 total count is HIGHER than skip=1:
- Track-ID re-assignment is still occurring despite Fix 2
- Check `max_iou_distance` — may need to relax further for this scene
- The spatial deduplication (Fix 6, next batch) would address the remainder

### If YOLO ms varies across runs:
- Thermal throttling on CPU — re-run after cooldown period
- Or model is not cached — first run always slower; use second run values

### If Tracker ms is high at skip=5:
- Large gap between processed frames means Kalman predictions are still
  somewhat off despite Fix 2 (one `predict()` per skipped frame adds up)
- Consider reducing `max_cosine_distance` (appearance threshold) or enabling
  `gating_only_position=True` in `_init_tracker()` to reduce matching cost

---

## Remaining Issues After This Batch of Fixes

These will be addressed in the next iteration (ScanContext refactor + spatial deduplication):

1. **Concurrent scan isolation** — global `_detector` singleton still shared
   across requests; two simultaneous scans corrupt each other's state.

2. **Spatial deduplication backstop** — if IoU matching still fails despite
   Fix 2, the same physical plant can be counted under two track IDs.
   A grid-cell position cache will catch these residual duplicates.

3. **Live stream Kalman accuracy** — we cannot call `advance_kalman_only()`
   for the frames the capture thread discards; only Fix 1 (tracker reset)
   and Fix 7 (lag monitoring) apply to live mode today.

4. **Track minimum-hit threshold** — tracks with only `n_init` hits (the bare
   minimum for confirmation) are more likely to be noise. A minimum of
   `n_init + 2` hits before counting would further reduce false positives.

5. **ScanContext per-scan isolation** — moving tracker + unique_ids into a
   per-scan object removes the shared-state risk entirely without needing locks.

---

## Running the Live Stream Test

### 1. Start server and MediaMTX
```bash
python backend/app.py
```

### 2. Push a test stream (requires ffmpeg)
```bash
ffmpeg -re -f lavfi -i testsrc=size=1280x720:rate=25 \
       -f lavfi -i sine -c:v libx264 -preset ultrafast \
       -c:a aac -f flv rtmp://localhost:1935/pinevision_scan
```

### 3. Start scan via frontend or curl
```bash
curl -X POST http://localhost:5000/api/drone/start-detection \
     -H "Content-Type: application/json" \
     -d '{"hls_url":"http://localhost:8888/pinevision_scan/index.m3u8","block_id":"TEST","user_id":"TEST","fps":1}'
```

### 4. Watch server logs for
- `🔧 Tracker init` — confirms Fix 1 ran
- `⚠️ [LAG]` — Fix 7 queue lag detection
- `⚠️ [SLOW]` — Fix 7 per-frame budget warning
- `📊 Live F...` — periodic detection log with full metrics
