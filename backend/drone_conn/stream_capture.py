"""
HLS stream frame capture using OpenCV and ffmpeg.
Extracts frames from live HLS video stream for YOLO detection.
"""

import cv2
import numpy as np
import os
import re
import requests
import threading
import time
from queue import Empty, Queue
from typing import Optional


_MAX_RETRIES = 10          # attempts for pre-flight check and cap.open()
_RETRY_DELAY = 2.0         # seconds between retries
_MAX_FRAME_FAILURES = 30   # consecutive read failures before reconnect attempt
_RECONNECT_DELAY = 3.0     # seconds to wait before reconnect
_FPS_LOG_INTERVAL = 10.0   # seconds between FPS log lines
_WARMUP_FRAMES = 10        # frames to drain after open before queuing
_MAX_RECONNECTS = 5        # stop after this many reconnects (prevents EOF loop on static files)

# Matches MediaMTX HLS URLs: http://HOST:8888/PATH/index.m3u8
_MEDIAMTX_HLS_RE = re.compile(r'^http://([^:/]+):8888/(.+?)/index\.m3u8$')


def _derive_rtsp_url(hls_url: str) -> Optional[str]:
    """
    Convert a MediaMTX HLS URL to its RTSP equivalent.
    http://localhost:8888/pinevision_scan/index.m3u8
      -> rtsp://localhost:8554/pinevision_scan
    Returns None if the URL doesn't match the MediaMTX HLS pattern.
    """
    m = _MEDIAMTX_HLS_RE.match(hls_url)
    if m:
        return f'rtsp://{m.group(1)}:8554/{m.group(2)}'
    return None


class HLSStreamCapture:
    """Captures frames from an HLS video stream."""

    def __init__(self, hls_url: str, fps: int = 1):
        self.hls_url = hls_url
        self.fps = fps
        self.frame_interval = 1.0 / fps

        self.cap: Optional[cv2.VideoCapture] = None
        self._capture_url: str = hls_url  # resolved at open-time, may switch to RTSP
        self.running = False
        self.frame_queue: Queue = Queue(maxsize=10)
        self.capture_thread: Optional[threading.Thread] = None

    # ── public API ────────────────────────────────────────────────────

    def start(self) -> bool:
        """Start capturing. Returns True only when the stream is confirmed ready."""
        print(f"🎥 Starting stream capture: {self.hls_url}")

        if not self._wait_for_playlist():
            return False

        self.cap = self._open_capture()
        if self.cap is None:
            return False

        self.running = True
        self.capture_thread = threading.Thread(
            target=self._capture_loop, daemon=True
        )
        self.capture_thread.start()
        return True

    def get_frame(self, timeout: float = 5.0) -> Optional[np.ndarray]:
        try:
            return self.frame_queue.get(timeout=timeout)
        except Empty:
            print("⚠️  Timeout waiting for frame")
            return None

    def stop(self):
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=3.0)
        if self.cap:
            self.cap.release()
            self.cap = None
        print("✅ Stream capture stopped")

    def is_running(self) -> bool:
        return self.running

    # ── private helpers ───────────────────────────────────────────────

    def _wait_for_playlist(self) -> bool:
        """
        Poll the m3u8 URL until it returns HTTP 200.
        HLS segments need a few seconds to be generated after the drone
        starts publishing, so we retry with a fixed delay.
        """
        print(f"⏳ Waiting for HLS playlist to become ready...")
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                r = requests.get(self.hls_url, timeout=4)
                if r.status_code == 200:
                    print(f"✅ HLS playlist ready (attempt {attempt})")
                    return True
                if r.status_code == 404:
                    print(
                        f"⚠️  HTTP 404 — no publisher streaming to this path yet "
                        f"(attempt {attempt}/{_MAX_RETRIES}) — retrying in {_RETRY_DELAY}s"
                    )
                else:
                    print(
                        f"⚠️  HTTP {r.status_code} from playlist "
                        f"(attempt {attempt}/{_MAX_RETRIES}) — retrying in {_RETRY_DELAY}s"
                    )
            except requests.RequestException as exc:
                print(
                    f"⚠️  Playlist check failed — MediaMTX may not be running "
                    f"(attempt {attempt}/{_MAX_RETRIES}): {exc}"
                )
            time.sleep(_RETRY_DELAY)

        print(f"❌ HLS playlist never became ready: {self.hls_url}")
        print(f"   → Ensure a drone or test publisher is actively streaming to MediaMTX.")
        print(f"   → Test stream: ffmpeg -re -f lavfi -i testsrc=size=640x480:rate=25 -f lavfi -i sine -c:v libx264 -preset ultrafast -c:a aac -f flv rtmp://localhost:1935/pinevision_scan")
        return False

    def _try_open(self, url: str, protocol: str) -> Optional[cv2.VideoCapture]:
        """
        Attempt to open VideoCapture for `url` up to _MAX_RETRIES times.
        RTSP uses TCP transport to avoid UDP packet loss on loopback.
        """
        if protocol == 'RTSP':
            # Force TCP — eliminates UDP packet loss that causes frame failures
            # on loopback and local networks.
            os.environ['OPENCV_FFMPEG_CAPTURE_OPTIONS'] = 'rtsp_transport;tcp'

        for attempt in range(1, _MAX_RETRIES + 1):
            cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
            if cap.isOpened():
                # Minimal internal buffer: we want the latest frame, not a
                # backlog. The capture loop discards stale frames itself.
                buf_size = 1 if protocol == 'RTSP' else 3
                cap.set(cv2.CAP_PROP_BUFFERSIZE, buf_size)
                print(f"✅ {protocol} VideoCapture opened (attempt {attempt}): {url}")
                return cap
            cap.release()
            print(
                f"⚠️  {protocol} VideoCapture.open failed "
                f"(attempt {attempt}/{_MAX_RETRIES}), "
                f"retrying in {_RETRY_DELAY}s..."
            )
            time.sleep(_RETRY_DELAY)
        return None

    def _open_capture(self) -> Optional[cv2.VideoCapture]:
        """
        Try RTSP first (derived from the HLS URL), fall back to HLS.

        RTSP is a continuous stream with no HLS segment boundaries, so OpenCV
        never hits the inter-segment gap that causes repeated ret=False reads.
        MediaMTX always exposes RTSP on :8554 alongside HLS on :8888.
        """
        rtsp_url = _derive_rtsp_url(self.hls_url)

        if rtsp_url:
            print(f"🔄 Trying RTSP (preferred over HLS): {rtsp_url}")
            cap = self._try_open(rtsp_url, protocol='RTSP')
            if cap is not None:
                self._capture_url = rtsp_url
                return cap
            print("⚠️  RTSP unavailable — falling back to HLS")

        cap = self._try_open(self.hls_url, protocol='HLS')
        if cap is not None:
            self._capture_url = self.hls_url
            return cap

        print(f"❌ Could not open stream: {self.hls_url}")
        return None

    def _reconnect(self) -> bool:
        """
        Release the dead capture, wait for the playlist to come back, and
        re-open. Returns True if reconnection succeeded.
        """
        print("🔄 Stream dropped — attempting reconnect...")
        if self.cap:
            self.cap.release()
            self.cap = None
        time.sleep(_RECONNECT_DELAY)

        if not self._wait_for_playlist():
            return False

        self.cap = self._open_capture()
        if self.cap is None:
            return False

        print("✅ Reconnected to stream")
        return True

    def _capture_loop(self):
        """
        Background thread: drain the ffmpeg/OpenCV buffer on every iteration
        (prevents stale frame accumulation) and enqueue one frame per fps
        interval for YOLO. Reconnects automatically when the stream dies.
        """
        last_capture_time = 0.0
        consecutive_failures = 0
        reconnect_count = 0
        frames_since_log = 0
        fps_log_time = time.time()

        # Drain the initial buffer so we start reading near-live frames
        # rather than replaying frames that accumulated during cap.open().
        print(f"⏳ Warming up stream (draining {_WARMUP_FRAMES} buffered frames)...")
        for _ in range(_WARMUP_FRAMES):
            try:
                self.cap.read()
            except Exception:
                break

        while self.running:
            # ── read one frame ────────────────────────────────────────
            try:
                ret, frame = self.cap.read()
            except Exception as exc:
                print(f"❌ cap.read() raised: {exc}")
                ret, frame = False, None

            # ── handle read failure ───────────────────────────────────
            if not ret or frame is None:
                consecutive_failures += 1
                if consecutive_failures % 10 == 1:
                    print(
                        f"⚠️  Frame read failure #{consecutive_failures} "
                        f"(url: {self._capture_url})"
                    )
                if consecutive_failures >= _MAX_FRAME_FAILURES:
                    reconnect_count += 1
                    if reconnect_count > _MAX_RECONNECTS:
                        print(
                            f"🛑 Stream ended after {reconnect_count - 1} reconnect(s) "
                            "(static file finished or stream permanently gone) — stopping capture"
                        )
                        self.running = False
                        break
                    print(
                        f"❌ {consecutive_failures} consecutive frame failures — "
                        f"reconnecting... (attempt {reconnect_count}/{_MAX_RECONNECTS})"
                    )
                    if self._reconnect():
                        consecutive_failures = 0
                    else:
                        print("❌ Reconnect failed — stopping capture")
                        self.running = False
                        break
                time.sleep(0.1)
                continue

            # ── successful read ───────────────────────────────────────
            consecutive_failures = 0
            frames_since_log += 1

            now = time.time()

            # periodic FPS log
            elapsed = now - fps_log_time
            if elapsed >= _FPS_LOG_INTERVAL:
                fps = frames_since_log / elapsed
                h, w = frame.shape[:2]
                print(
                    f"📈 Capture: {fps:.1f} FPS | frame size: {w}×{h} | "
                    f"queue: {self.frame_queue.qsize()}/{self.frame_queue.maxsize}"
                )
                frames_since_log = 0
                fps_log_time = now

            # enqueue latest frame at the configured fps rate
            if now - last_capture_time >= self.frame_interval:
                if self.frame_queue.full():
                    try:
                        self.frame_queue.get_nowait()
                    except Empty:
                        pass
                self.frame_queue.put(frame)
                last_capture_time = now


def test_stream(hls_url: str, duration: int = 10):
    """Quick smoke-test: connect and capture frames for `duration` seconds."""
    print(f"🧪 Testing HLS stream: {hls_url}")

    capture = HLSStreamCapture(hls_url, fps=1)

    if not capture.start():
        print("❌ Failed to start stream capture")
        return False

    print(f"⏳ Capturing frames for {duration} seconds...")
    start_time = time.time()
    frame_count = 0

    while time.time() - start_time < duration:
        frame = capture.get_frame(timeout=3.0)
        if frame is not None:
            frame_count += 1
            h, w = frame.shape[:2]
            print(f"✅ Frame {frame_count}: {w}×{h}")
        else:
            print("⚠️  No frame received")
        time.sleep(1)

    capture.stop()
    print(f"\n📊 Test complete: {frame_count} frames in {duration}s")
    return frame_count > 0


if __name__ == "__main__":
    test_url = "http://localhost:8888/pinevision_scan/index.m3u8"
    test_stream(test_url, duration=10)
