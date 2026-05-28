/* ============================================================
   drone-view.js
   Drone view page — real MediaMTX stream integration + Firebase detection
   
   NEW: Integrated Firebase real-time detection updates
   ============================================================ */

'use strict';

// ── Constants ─────────────────────────────────────────────────

const API_BASE         = '';        // same-origin Flask server
const POLL_INTERVAL_MS = 5_000;
const MAX_RECONNECT    = 3;

const HLS_CONFIG = {
    maxLoadingDelay:         10,
    manifestLoadingTimeOut:  8_000,
    manifestLoadingMaxRetry: 2,
    levelLoadingTimeOut:     8_000,
};

// ── State ─────────────────────────────────────────────────────

const DRONE_STATE = {
    status:            'idle',   // idle|connecting|active|reconnecting|failed|ending
    streamUrl:         null,
    rtmpUrl:           null,
    streamPath:        null,
    blockId:           null,     // NEW: Block ID from URL
    userId:            null,     // NEW: Current user ID
    scanId:            null,     // NEW: Active scan session ID
    scanStartTime:     null,
    timerInterval:     null,
    statsInterval:     null,     // REMOVED: No more mock stats
    pollInterval:      null,
    reconnectAttempts: 0,
    hls:               null,
    firebaseListener:  null,     // NEW: Firebase listener
    stats: { total: 0, bearing: 0, nonBearing: 0, discolored: 0, progress: 0 },
};

const STATUS_LABELS = {
    idle:         'No Signal',
    connecting:   'Connecting...',
    active:       'Live',
    reconnecting: 'Reconnecting...',
    failed:       'Connection Failed',
    ending:       'Ending Scan...',
};

// ── UI Rendering ──────────────────────────────────────────────

function renderUI() {
    const s = DRONE_STATE.status;

    // Status indicator
    const indicator = document.getElementById('dv-status-indicator');
    indicator.className = `dv-status-${s} d-flex align-items-center gap-2 me-3`;
    document.querySelector('.dv-status-label').textContent = STATUS_LABELS[s] ?? s;

    // Derived state groups
    const isLive     = s === 'active';
    const isLoading  = s === 'connecting' || s === 'reconnecting';
    const isInactive = s === 'idle' || s === 'failed';
    const isSession  = s === 'active' || s === 'reconnecting';

    // Placeholder title/hint varies between idle and failed
    document.querySelector('.dv-placeholder-title').textContent =
        s === 'failed' ? 'Connection Failed' : 'Awaiting Connection';
    document.querySelector('.dv-placeholder-hint').textContent =
        s === 'failed'
            ? 'Stream could not be established. Check setup and try again.'
            : 'Click "Connect Drone" to begin a scan session';

    // Connecting overlay label changes for reconnect
    const connLabel = document.querySelector('.dv-connecting-label');
    if (connLabel) connLabel.textContent = s === 'reconnecting' ? 'Reconnecting...' : 'Connecting...';

    // Topbar buttons
    toggleEl('btn-connect',        isInactive);
    toggleEl('btn-end-scan',       isSession);
    toggleEl('btn-end-scan-stats', isSession);

    // Video + overlays
    toggleClass('drone-feed',         'dv-feed-active', isLive);
    toggleEl('dv-placeholder',        isInactive);
    toggleEl('dv-connecting-overlay', isLoading);
    toggleEl('dv-live-overlay',       isLive);

    // Timer stays visible while a session is active
    toggleEl('dv-timer', isSession);

    // Reset stat display only when fully idle
    if (s === 'idle') resetStatDisplay();
}

function transitionTo(newStatus) {
    DRONE_STATE.status = newStatus;
    renderUI();
}

// ── Backend API ───────────────────────────────────────────────

async function apiConnect(rtmpUrl) {
    const resp = await fetch(`${API_BASE}/api/drone/connect`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ rtmp_url: rtmpUrl }),
        signal:  AbortSignal.timeout(10_000),
    });
    if (!resp.ok && resp.status !== 400) throw new Error(`Server ${resp.status}`);
    return resp.json();
}

async function apiStatus(path) {
    const resp = await fetch(
        `${API_BASE}/api/drone/status?path=${encodeURIComponent(path)}`,
        { signal: AbortSignal.timeout(5_000) },
    );
    return resp.json();
}

// NEW: Start detection API
async function apiStartDetection(hlsUrl, blockId, userId) {
    const resp = await fetch(`${API_BASE}/api/drone/start-detection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            hls_url: hlsUrl,
            block_id: blockId,
            user_id: userId,
            fps: 1
        }),
        signal: AbortSignal.timeout(10_000)
    });
    return resp.json();
}

// NEW: Stop detection API
async function apiStopDetection(blockId, scanId, userId) {
    const resp = await fetch(`${API_BASE}/api/drone/stop-detection`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            block_id: blockId,
            scan_id: scanId,
            user_id: userId,
        }),
        signal: AbortSignal.timeout(10_000)
    });
    return resp.json();
}

// ── Connection Workflow ───────────────────────────────────────

async function handleConnect() {
    if (DRONE_STATE.status === 'connecting') return;

    const rawUrl = document.getElementById('input-rtmp-url').value.trim();

    if (!validateRtmpUrl(rawUrl)) {
        showInputError('input-rtmp-url', 'Enter a valid RTMP URL (rtmp://...)');
        return;
    }
    clearInputError('input-rtmp-url');
    hideConnectError();
    setConnectButtonLoading(true);
    lockConnectModal(true);
    transitionTo('connecting');

    let result;
    try {
        result = await apiConnect(rawUrl);
    } catch {
        handleConnectFailed(
            'Cannot reach the backend server. Ensure Flask (backend/app.py) is running on port 5000.',
        );
        return;
    }

    if (!result.ok) {
        const MESSAGES = {
            invalid_url:      'Invalid RTMP URL format. Expected: rtmp://HOST:PORT/PATH',
            mediamtx_offline: 'MediaMTX is not running. Start mediamtx.exe and try again.',
            path_not_found:   'Stream path not found in MediaMTX configuration.',
            stream_not_ready: 'Drone is not streaming. Start the live stream in DJI Fly first.',
        };
        handleConnectFailed(MESSAGES[result.error] ?? result.message ?? 'Connection failed.');
        return;
    }

    DRONE_STATE.rtmpUrl           = rawUrl;
    DRONE_STATE.streamUrl         = result.hls_url;
    DRONE_STATE.streamPath        = result.path;
    DRONE_STATE.reconnectAttempts = 0;

    loadHlsStream(result.hls_url, /* isReconnect */ false);
}

// ── HLS Playback ──────────────────────────────────────────────

function loadHlsStream(hlsUrl, isReconnect) {
    if (typeof Hls === 'undefined') {
        handleConnectFailed('hls.js not loaded. Check your internet connection.');
        return;
    }

    if (!Hls.isSupported()) {
        const videoEl = document.getElementById('drone-feed');
        if (videoEl.canPlayType('application/vnd.apple.mpegurl')) {
            videoEl.src = hlsUrl;
            videoEl.addEventListener('loadedmetadata', () => onHlsReady(isReconnect), { once: true });
            videoEl.addEventListener('error', () => onHlsFatalError(isReconnect), { once: true });
            return;
        }
        handleConnectFailed('HLS is not supported in this browser.');
        return;
    }

    destroyHls();

    const hls     = new Hls(HLS_CONFIG);
    const videoEl = document.getElementById('drone-feed');
    DRONE_STATE.hls = hls;

    hls.loadSource(hlsUrl);
    hls.attachMedia(videoEl);

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
        videoEl.play().catch(() => {});
        onHlsReady(isReconnect);
    });

    hls.on(Hls.Events.ERROR, (_e, data) => {
        if (data.fatal) onHlsFatalError(isReconnect);
    });
}

async function onHlsReady(isReconnect) {
    if (isReconnect) {
        DRONE_STATE.reconnectAttempts = 0;
        transitionTo('active');
        utils.showToast('Stream reconnected', 'success');
        return;
    }

    // Initial connection success
    setConnectButtonLoading(false);
    lockConnectModal(false);
    closeBsModal('modal-connect');

    DRONE_STATE.scanStartTime = new Date();
    startScanTimer();
    startStatusPolling();

    // NEW: Start detection on backend
    await startDetection();

    transitionTo('active');
    document.getElementById('dv-stream-quality').textContent = 'HLS';
    utils.showToast('Drone stream connected', 'success');
}

function onHlsFatalError(isReconnect) {
    if (isReconnect) {
        handleStreamLost();
    } else {
        handleConnectFailed(
            'Stream unavailable. Verify MediaMTX is running and the drone is broadcasting.',
        );
    }
}

function handleConnectFailed(message) {
    setConnectButtonLoading(false);
    lockConnectModal(false);
    showConnectError(message);
    destroyHls();
    stopStatusPolling();
    DRONE_STATE.streamUrl  = null;
    DRONE_STATE.streamPath = null;
    transitionTo('failed');
}

// ── NEW: Detection Start/Stop ─────────────────────────────────

async function startDetection() {
    if (!DRONE_STATE.streamUrl || !DRONE_STATE.blockId || !DRONE_STATE.userId) {
        console.error('❌ Missing required data for detection');
        return;
    }

    try {
        console.log('🎯 Starting detection...');

        const result = await apiStartDetection(
            DRONE_STATE.streamUrl,
            DRONE_STATE.blockId,
            DRONE_STATE.userId
        );

        if (result.ok) {
            console.log('✅ Detection started:', result.scan_id);
            DRONE_STATE.scanId = result.scan_id;
            
            // Start Firebase listener
            startFirebaseListener();
        } else {
            console.error('❌ Failed to start detection:', result.message);
            utils.showToast('Failed to start detection: ' + result.message, 'error');
        }
    } catch (error) {
        console.error('❌ Detection start error:', error);
        utils.showToast('Failed to start detection', 'error');
    }
}

async function stopDetection() {
    if (!DRONE_STATE.scanId || !DRONE_STATE.blockId) {
        console.error('❌ No active scan to stop');
        return false;
    }

    try {
        console.log('🛑 Stopping detection...');

        const result = await apiStopDetection(
            DRONE_STATE.blockId,
            DRONE_STATE.scanId,
            DRONE_STATE.userId
        );

        if (result.ok) {
            console.log('✅ Detection stopped successfully');
            stopFirebaseListener();
            return true;
        } else {
            console.error('❌ Failed to stop detection:', result.message);
            return false;
        }
    } catch (error) {
        console.error('❌ Detection stop error:', error);
        return false;
    }
}

// ── NEW: Firebase Real-time Listener ──────────────────────────

function startFirebaseListener() {
    if (!DRONE_STATE.blockId || typeof firebase === 'undefined') {
        console.error('❌ Firebase not available or no block ID');
        return;
    }

    console.log('🔥 Starting Firebase listener for block:', DRONE_STATE.blockId);

    // Listen to block document changes
    DRONE_STATE.firebaseListener = firebase.firestore()
        .collection('blocks')
        .doc(DRONE_STATE.blockId)
        .onSnapshot((doc) => {
            if (doc.exists) {
                const data = doc.data();
                console.log('📊 Firebase update received:', data);
                updateStatsFromFirebase(data);
            }
        }, (error) => {
            console.error('❌ Firebase listener error:', error);
        });
}

function stopFirebaseListener() {
    if (DRONE_STATE.firebaseListener) {
        console.log('🔥 Stopping Firebase listener');
        DRONE_STATE.firebaseListener();
        DRONE_STATE.firebaseListener = null;
    }
}

function updateStatsFromFirebase(data) {
    // Update stats from Firebase data
    DRONE_STATE.stats.bearing = data.bearingPercent || 0;
    DRONE_STATE.stats.nonBearing = data.nonBearingPercent || 0;
    DRONE_STATE.stats.discolored = data.nonViable || 0;
    DRONE_STATE.stats.total = data.totalPineapples || 0;
    
    // Calculate progress based on bearing rate
    DRONE_STATE.stats.progress = Math.round(data.bearingPercent || 0);
    
    updateStatDisplay();
}

// ── Stream Health Polling ─────────────────────────────────────

function startStatusPolling() {
    DRONE_STATE.pollInterval = setInterval(async () => {
        const s = DRONE_STATE.status;
        if (s !== 'active' && s !== 'reconnecting') return;

        let result;
        try {
            result = await apiStatus(DRONE_STATE.streamPath);
        } catch {
            result = { ok: false, ready: false };
        }

        if (result.ready) {
            if (s === 'reconnecting') {
                transitionTo('connecting');
                loadHlsStream(DRONE_STATE.streamUrl, /* isReconnect */ true);
            }
        } else {
            handleStreamLost();
        }
    }, POLL_INTERVAL_MS);
}

function stopStatusPolling() {
    clearInterval(DRONE_STATE.pollInterval);
    DRONE_STATE.pollInterval = null;
}

function handleStreamLost() {
    const s = DRONE_STATE.status;

    if (s === 'reconnecting') {
        DRONE_STATE.reconnectAttempts++;
        if (DRONE_STATE.reconnectAttempts >= MAX_RECONNECT) {
            stopScanIntervals();
            stopStatusPolling();
            stopDetection();
            destroyHls();
            transitionTo('failed');
            utils.showToast('Stream lost. Scan ended automatically.', 'error');
        }
        return;
    }

    if (s === 'active') {
        DRONE_STATE.reconnectAttempts = 0;
        transitionTo('reconnecting');
        utils.showToast('Stream interrupted. Attempting to reconnect…', 'info');
    }
}

// ── End Scan Workflow ─────────────────────────────────────────

function onEndScanModalShow() {
    document.getElementById('summary-duration').textContent    = document.getElementById('dv-timer').textContent;
    document.getElementById('summary-total').textContent       = DRONE_STATE.stats.total.toLocaleString();
    document.getElementById('summary-bearing').textContent     = DRONE_STATE.stats.bearing.toFixed(1) + '%';
    document.getElementById('summary-non-bearing').textContent = DRONE_STATE.stats.nonBearing.toFixed(1) + '%';
    document.getElementById('summary-discolored').textContent  = DRONE_STATE.stats.discolored.toFixed(1) + '%';
}

async function handleEndScan() {
    setEndScanButtonLoading(true);
    transitionTo('ending');

    // Stop detection on backend
    await stopDetection();

    destroyHls();
    stopScanIntervals();
    stopStatusPolling();

    const videoEl = document.getElementById('drone-feed');
    videoEl.pause();
    videoEl.removeAttribute('src');
    videoEl.load();

    DRONE_STATE.stats             = { total: 0, bearing: 0, nonBearing: 0, discolored: 0, progress: 0 };
    DRONE_STATE.scanStartTime     = null;
    DRONE_STATE.streamUrl         = null;
    DRONE_STATE.rtmpUrl           = null;
    DRONE_STATE.streamPath        = null;
    DRONE_STATE.reconnectAttempts = 0;
    DRONE_STATE.scanId            = null;

    setEndScanButtonLoading(false);
    closeBsModal('modal-end-scan');
    transitionTo('idle');
    utils.showToast('Scan session ended', 'info');
    
    // Redirect to block details
    if (DRONE_STATE.blockId) {
        setTimeout(() => {
            window.location.href = 'blocks-view.html?id=' + DRONE_STATE.blockId;
        }, 1000);
    }
}

// ── Timer ─────────────────────────────────────────────────────

function startScanTimer() {
    const timerEl = document.getElementById('dv-timer');
    DRONE_STATE.timerInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - DRONE_STATE.scanStartTime) / 1000);
        const h = String(Math.floor(elapsed / 3600)).padStart(2, '0');
        const m = String(Math.floor((elapsed % 3600) / 60)).padStart(2, '0');
        const s = String(elapsed % 60).padStart(2, '0');
        timerEl.textContent = `${h}:${m}:${s}`;
    }, 1_000);
}

function stopScanIntervals() {
    clearInterval(DRONE_STATE.timerInterval);
    DRONE_STATE.timerInterval = null;
}

// ── HLS Cleanup ───────────────────────────────────────────────

function destroyHls() {
    if (DRONE_STATE.hls) {
        DRONE_STATE.hls.destroy();
        DRONE_STATE.hls = null;
    }
}

// ── Fullscreen ────────────────────────────────────────────────

function setupFullscreen() {
    const btn     = document.getElementById('dv-fullscreen-btn');
    const wrapper = document.getElementById('drone-feed-wrapper');
    const icon    = btn.querySelector('i');

    btn.addEventListener('click', () => {
        if (!document.fullscreenElement) wrapper.requestFullscreen().catch(() => {});
        else document.exitFullscreen().catch(() => {});
    });

    document.addEventListener('fullscreenchange', () => {
        const fs = !!document.fullscreenElement;
        icon.className = fs ? 'ti ti-minimize' : 'ti ti-maximize';
        btn.setAttribute('aria-label', fs ? 'Exit fullscreen' : 'Toggle fullscreen');
    });
}

// ── Display Helpers ───────────────────────────────────────────

function updateStatDisplay() {
    const s = DRONE_STATE.stats;
    document.getElementById('stat-total').textContent       = s.total.toLocaleString();
    document.getElementById('stat-bearing').textContent     = s.bearing.toFixed(1) + '%';
    document.getElementById('stat-non-bearing').textContent = s.nonBearing.toFixed(1) + '%';
    document.getElementById('stat-discolored').textContent  = s.discolored.toFixed(1) + '%';

    const fill = document.getElementById('stat-progress-fill');
    fill.style.width = s.progress + '%';
    fill.setAttribute('aria-valuenow', s.progress);
    document.getElementById('stat-progress-pct').textContent = Math.round(s.progress) + '%';
    document.querySelector('#dv-stats-panel .progress').setAttribute('aria-valuenow', s.progress);
}

function resetStatDisplay() {
    ['stat-total', 'stat-bearing', 'stat-non-bearing', 'stat-discolored'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.textContent = '—';
    });
    const fill = document.getElementById('stat-progress-fill');
    if (fill) { fill.style.width = '0%'; fill.setAttribute('aria-valuenow', 0); }
    const pct = document.getElementById('stat-progress-pct');
    if (pct) pct.textContent = '0%';
    const timer = document.getElementById('dv-timer');
    if (timer) timer.textContent = '00:00:00';
}

// ── Input Error Helpers ───────────────────────────────────────

function showInputError(inputId, message) {
    document.getElementById(inputId)?.classList.add('is-invalid');
    const err = document.getElementById(inputId + '-error');
    if (err) { err.textContent = message; err.classList.remove('d-none'); }
}

function clearInputError(inputId) {
    document.getElementById(inputId)?.classList.remove('is-invalid');
    document.getElementById(inputId + '-error')?.classList.add('d-none');
}

function showConnectError(message) {
    const msg = document.getElementById('connect-error-message');
    if (msg) msg.textContent = message;
    document.getElementById('connect-error-banner')?.classList.remove('d-none');
}

function hideConnectError() {
    document.getElementById('connect-error-banner')?.classList.add('d-none');
}

// ── Button Loading States ─────────────────────────────────────

function setConnectButtonLoading(loading) {
    const btn = document.getElementById('btn-connect-submit');
    if (!btn) return;
    btn.disabled = loading;
    document.getElementById('btn-connect-label').textContent = loading ? 'Connecting...' : 'Connect';
    document.getElementById('btn-connect-spinner').classList.toggle('d-none', !loading);
}

function setEndScanButtonLoading(loading) {
    const btn = document.getElementById('btn-confirm-end-scan');
    if (!btn) return;
    btn.disabled = loading;
    document.getElementById('btn-end-label').textContent = loading ? 'Ending...' : 'End Scan';
    document.getElementById('btn-end-spinner').classList.toggle('d-none', !loading);
}

// ── Modal Lock During Connecting ──────────────────────────────

function lockConnectModal(lock) {
    const el = document.getElementById('modal-connect');
    if (!el) return;
    const modal = bootstrap.Modal.getInstance(el);
    if (!modal) return;
    modal._config.backdrop = lock ? 'static' : true;
    modal._config.keyboard = !lock;
    const closeBtn = el.querySelector('.btn-close');
    if (closeBtn) closeBtn.disabled = lock;
}

// ── DOM / Bootstrap Utilities ─────────────────────────────────

function toggleEl(id, show) {
    document.getElementById(id)?.classList.toggle('d-none', !show);
}

function toggleClass(id, cls, add) {
    document.getElementById(id)?.classList.toggle(cls, add);
}

function closeBsModal(id) {
    const el = document.getElementById(id);
    if (!el) return;
    bootstrap.Modal.getInstance(el)?.hide();
}

// ── URL Validation ────────────────────────────────────────────

function validateRtmpUrl(url) {
    return typeof url === 'string' && /^rtmp:\/\/.+/.test(url) && url.length > 10;
}

// ── Modal Event Wiring ────────────────────────────────────────

function setupModalEvents() {
    const connectModalEl = document.getElementById('modal-connect');
    connectModalEl.addEventListener('show.bs.modal', () => {
        clearInputError('input-rtmp-url');
        hideConnectError();
        setConnectButtonLoading(false);
    });
    document.getElementById('btn-connect-submit')
        .addEventListener('click', handleConnect);
    document.getElementById('input-rtmp-url')
        .addEventListener('keydown', e => { if (e.key === 'Enter') handleConnect(); });
    document.getElementById('input-rtmp-url')
        .addEventListener('input', () => clearInputError('input-rtmp-url'));

    const endScanModalEl = document.getElementById('modal-end-scan');
    endScanModalEl.addEventListener('show.bs.modal', () => {
        const s = DRONE_STATE.status;
        if (s === 'active' || s === 'reconnecting') onEndScanModalShow();
        setEndScanButtonLoading(false);
    });
    document.getElementById('btn-confirm-end-scan')
        .addEventListener('click', handleEndScan);
}

// ── Back Navigation ───────────────────────────────────────────

function setupBackNavigation() {
    document.getElementById('btn-back').addEventListener('click', () => {
        if (DRONE_STATE.blockId) {
            window.location.href = 'blocks-view.html?id=' + DRONE_STATE.blockId;
        } else if (history.length > 1) {
            history.back();
        } else {
            window.location.href = 'blocks.html';
        }
    });
}

// ── Page Initialization ───────────────────────────────────────

function initPage() {
    utils.initializeSettings();
    
    // Get block ID and user ID
    const urlParams = new URLSearchParams(window.location.search);
    DRONE_STATE.blockId = urlParams.get('blockId');
    
    // Get current user
    if (typeof auth !== 'undefined') {
        const currentUser = auth.getCurrentUser();
        if (currentUser) {
            DRONE_STATE.userId = currentUser.uid;
            console.log('✅ User ID:', DRONE_STATE.userId);
        }
    }
    
    console.log('📦 Block ID:', DRONE_STATE.blockId);
    
    setupBackNavigation();
    setupModalEvents();
    setupFullscreen();
    renderUI();
}

document.addEventListener('DOMContentLoaded', initPage);