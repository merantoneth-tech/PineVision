# PineVision Drone Scan Pipeline — Fixes Needed

## CRITICAL

### 1. Double `initPage()` call — `drone-view.js` line 782
`drone-view.js` registers its own `DOMContentLoaded` listener AND defines `window.initPage`, so `app.js` calls it once and the listener calls it again. Every modal button gets its event listener attached twice, causing every Connect/End Scan click to fire the handler twice.

**Fix:** Delete line 782 in `drone-view.js`:
```js
// DELETE this line:
document.addEventListener('DOMContentLoaded', initPage);
```
`app.js` already calls `window.initPage()` — the top-level function declaration makes it globally available automatically.

---

### 2. "New Scan" button loses `blockId` on click — `app.js` line 145
`setupPageTransitions()` captures `href` in a closure at DOMContentLoaded time. `blocks-view.html` dynamically updates `btn-new-scan`'s href to `drone-view.html?blockId=...` after Firebase loads, but the listener still navigates using the stale `"drone-view.html"` value. Result: `DRONE_STATE.blockId` is null, detection never starts, nothing is saved.

**Fix:** Read the live attribute at click time in `app.js` line 145:
```js
// BEFORE:
window.location.href = href;

// AFTER:
window.location.href = link.getAttribute('href');
```

---

## HIGH

### 3. Silent detection failure — `drone-view.js` lines 348–353
If `DRONE_STATE.blockId` or `userId` is null, `startDetection()` silently returns. The user sees a connected drone feed but gets no stats, no Firestore writes, and no warning.

**Fix:** Add a toast before the `return`:
```js
if (!DRONE_STATE.streamUrl || !DRONE_STATE.blockId || !DRONE_STATE.userId) {
    utils.showToast('Cannot start detection: missing block or user context. Return to Blocks and try again.', 'error');
    return;
}
```

---

### 4. Orphaned `status: 'active'` scans on detection crash — `detection.py` lines 356–407
If `stream.start()` fails or an exception occurs inside `_detection_loop()`, the scan session document in Firestore stays permanently stuck at `status: 'active'`. The frontend listener waits forever and the scans page shows broken entries.

**Fix:** Track whether the loop completed normally and update the scan document to `status: 'failed'` in the `finally` block when it didn't.

```python
completed_normally = False
# ... (stream open check, set failed + return if stream fails) ...
try:
    while ...:
        ...
    completed_normally = True
except Exception as e:
    ...
finally:
    stream.stop()
    if not completed_normally:
        try:
            db = get_firestore_client()
            from firebase_admin import firestore as _fs
            db.collection('scans').document(scan_id).update({
                'status': 'failed',
                'endTime': _fs.SERVER_TIMESTAMP,
            })
        except Exception:
            pass
```

---

### 5. `stopDetection()` not awaited in `handleStreamLost()` — `drone-view.js` lines 493–498
`stopDetection()` is async but is called without `await`, so the `/api/drone/stop-detection` request may never complete before the page transitions to `failed`. Scan data can be lost when the stream drops.

**Fix:** Make `handleStreamLost` async and await the call:
```js
async function handleStreamLost() {
    ...
    await stopDetection();
    ...
}
```

---

## MEDIUM

### 6. Wrong auth redirect in `scans.js` line 28
`window.location.href = '../auth/login.html'` points to a non-existent path.

**Fix:**
```js
window.location.href = '/index.html';
```

---

### 7. Final detection stats not written to block on scan completion — `firebase_client.py` lines 169–175
`complete_scan_session()` only increments `totalScans` and sets `lastScanned` on the block document. The block's `bearingPercent`, `nonBearingPercent`, `nonViable`, `totalPineapples` are not updated with the final values — they remain at whatever the last periodic batch write set (up to 2 seconds stale).

**Fix:** Add final stats to the block update inside `complete_scan_session()`:
```python
batch.update(block_ref, {
    'totalScans':        firestore.Increment(1),
    'lastScanned':       firestore.SERVER_TIMESTAMP,
    'bearingPercent':    round(bearing_pct, 1),
    'nonBearingPercent': round(non_bearing_pct, 1),
    'nonViable':         round(non_viable_pct, 1),
    'totalPineapples':   total_count,
})
```

---

## File Index

| File | Issue # |
|---|---|
| `frontend/js/drone-view.js` | 1, 3, 5 |
| `frontend/js/app.js` | 2 |
| `backend/drone_conn/detection.py` | 4 |
| `frontend/js/scans.js` | 6 |
| `backend/drone_conn/firebase_client.py` | 7 |
