"""
HLS stream frame capture using OpenCV and ffmpeg.
Extracts frames from live HLS video stream for YOLO detection.
"""

import cv2
import numpy as np
from typing import Optional, Generator
import time
import subprocess
import threading
from queue import Queue, Empty


class HLSStreamCapture:
    """Captures frames from an HLS video stream"""
    
    def __init__(self, hls_url: str, fps: int = 1):
        """
        Initialize HLS stream capture.
        
        Args:
            hls_url: HLS stream URL (e.g., http://localhost:8888/stream/index.m3u8)
            fps: Frames per second to capture (default: 1 = one frame per second)
        """
        self.hls_url = hls_url
        self.fps = fps
        self.frame_interval = 1.0 / fps
        
        self.cap = None
        self.running = False
        self.frame_queue = Queue(maxsize=10)
        self.capture_thread = None
        
    def start(self) -> bool:
        """
        Start capturing frames from HLS stream.
        
        Returns:
            True if started successfully, False otherwise
        """
        try:
            # Open video capture with ffmpeg backend
            self.cap = cv2.VideoCapture(self.hls_url, cv2.CAP_FFMPEG)
            
            if not self.cap.isOpened():
                print(f"❌ Failed to open HLS stream: {self.hls_url}")
                return False
            
            print(f"✅ HLS stream opened successfully")
            
            # Start capture thread
            self.running = True
            self.capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self.capture_thread.start()
            
            return True
            
        except Exception as e:
            print(f"❌ Error starting stream capture: {e}")
            return False
    
    def _capture_loop(self):
        """Background thread that continuously captures frames"""
        last_capture_time = 0
        
        while self.running:
            try:
                current_time = time.time()
                
                # Check if it's time to capture next frame
                if current_time - last_capture_time >= self.frame_interval:
                    ret, frame = self.cap.read()
                    
                    if ret:
                        # Add frame to queue (drop oldest if full)
                        if self.frame_queue.full():
                            try:
                                self.frame_queue.get_nowait()
                            except Empty:
                                pass
                        
                        self.frame_queue.put(frame)
                        last_capture_time = current_time
                    else:
                        print("⚠️ Failed to read frame from stream")
                        time.sleep(0.1)
                else:
                    # Sleep briefly to avoid busy-waiting
                    time.sleep(0.01)
                    
            except Exception as e:
                print(f"❌ Error in capture loop: {e}")
                time.sleep(0.1)
    
    def get_frame(self, timeout: float = 5.0) -> Optional[np.ndarray]:
        """
        Get the next available frame from the stream.
        
        Args:
            timeout: Maximum seconds to wait for a frame
        
        Returns:
            Frame as numpy array, or None if timeout/error
        """
        try:
            return self.frame_queue.get(timeout=timeout)
        except Empty:
            print("⚠️ Timeout waiting for frame")
            return None
    
    def stop(self):
        """Stop capturing frames and release resources"""
        self.running = False
        
        if self.capture_thread:
            self.capture_thread.join(timeout=2.0)
        
        if self.cap:
            self.cap.release()
            print("✅ Stream capture stopped")
    
    def is_running(self) -> bool:
        """Check if capture is currently running"""
        return self.running and self.cap is not None and self.cap.isOpened()


def test_stream(hls_url: str, duration: int = 5):
    """
    Test HLS stream connection and capture a few frames.
    
    Args:
        hls_url: HLS stream URL
        duration: Number of seconds to test
    """
    print(f"🧪 Testing HLS stream: {hls_url}")
    
    capture = HLSStreamCapture(hls_url, fps=1)
    
    if not capture.start():
        print("❌ Failed to start stream capture")
        return False
    
    print(f"⏳ Capturing frames for {duration} seconds...")
    
    start_time = time.time()
    frame_count = 0
    
    while time.time() - start_time < duration:
        frame = capture.get_frame(timeout=2.0)
        
        if frame is not None:
            frame_count += 1
            h, w = frame.shape[:2]
            print(f"✅ Frame {frame_count}: {w}x{h} pixels")
        else:
            print("⚠️ No frame received")
        
        time.sleep(1)
    
    capture.stop()
    
    print(f"\n📊 Test complete: {frame_count} frames captured in {duration} seconds")
    return frame_count > 0


if __name__ == "__main__":
    # Test with example HLS URL
    test_url = "http://localhost:8888/live/index.m3u8"
    test_stream(test_url, duration=10)