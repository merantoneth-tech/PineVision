"""
Real-time pineapple detection with YOLO + DeepSORT tracking.
Prevents duplicate counting and updates Firebase in real-time.
"""

import torch
import cv2
import numpy as np
from deep_sort_realtime.deepsort_tracker import DeepSort
import time
import threading
from typing import Dict, Set, Optional
from pathlib import Path

from .stream_capture import HLSStreamCapture
from .firebase_client import (
    get_firestore_client,
    update_detection_batch,
    create_scan_session,
    complete_scan_session,
)


def check_thresholds_and_create_alerts(
    block_id: str,
    bearing_percent: float,
    non_bearing_percent: float,
    non_viable_percent: float,
    user_id: str = '',
):
    """
    Check detection percentages against thresholds and create or
    auto-resolve monitoring_alerts documents accordingly.

    OPTIMIZED: Uses a single Firestore query to fetch all open alerts
    for this block, then processes everything in-memory, and commits
    all creates + resolves in a single batch write.

    Previous implementation: 6 sequential compound queries (one per
    threshold × check/resolve) — each requiring a network round-trip.
    Current implementation: 1 query + 1 batch commit regardless of
    how many alerts need to change.

    Requires a Firestore composite index on monitoring_alerts:
      blockId  ASC
      resolved ASC
    (Create once in Firebase Console → Firestore → Indexes → Composite)
    """
    from firebase_admin import firestore as _fs

    db = get_firestore_client()

    thresholds = {
        'bearing':    {'watch': 75,  'critical': 60},
        'nonbearing': {'watch': 18,  'critical': 25},
        'nonViable':  {'watch': 10,  'critical': 15},
    }

    print(f"\n🔍 Checking thresholds for block {block_id}:")
    print(f"   Bearing: {bearing_percent:.1f}%")
    print(f"   Non-bearing: {non_bearing_percent:.1f}%")
    print(f"   Non-viable: {non_viable_percent:.1f}%")

    # ── Single query: all open alerts for this block ─────────────────
    # Replaces 6 separate compound queries (2 per threshold type).
    open_docs = db.collection('monitoring_alerts') \
        .where('blockId', '==', block_id) \
        .where('resolved', '==', False) \
        .get()

    # Build in-memory map: title → document reference (O(1) lookup)
    open_by_title = {doc.data().get('title'): doc.reference for doc in open_docs}

    # ── Determine which alerts SHOULD currently be active ────────────
    desired: list[tuple[str, str, str]] = []  # (severity, title, description)

    if bearing_percent < thresholds['bearing']['critical']:
        desired.append(('crit', 'Critical bearing rate',
            f'Bearing rate at {bearing_percent:.1f}% — below critical threshold of '
            f'{thresholds["bearing"]["critical"]}%'))
    elif bearing_percent < thresholds['bearing']['watch']:
        desired.append(('warn', 'Low bearing rate',
            f'Bearing rate at {bearing_percent:.1f}% — below watch threshold of '
            f'{thresholds["bearing"]["watch"]}%'))

    if non_bearing_percent > thresholds['nonbearing']['critical']:
        desired.append(('crit', 'Critical non-bearing rate',
            f'Non-bearing rate at {non_bearing_percent:.1f}% — above critical threshold of '
            f'{thresholds["nonbearing"]["critical"]}%'))
    elif non_bearing_percent > thresholds['nonbearing']['watch']:
        desired.append(('warn', 'High non-bearing rate',
            f'Non-bearing rate at {non_bearing_percent:.1f}% — above watch threshold of '
            f'{thresholds["nonbearing"]["watch"]}%'))

    if non_viable_percent > thresholds['nonViable']['critical']:
        desired.append(('crit', 'Critical non-viable rate',
            f'Non-viable rate at {non_viable_percent:.1f}% — above critical threshold of '
            f'{thresholds["nonViable"]["critical"]}%'))
    elif non_viable_percent > thresholds['nonViable']['watch']:
        desired.append(('warn', 'High non-viable rate',
            f'Non-viable rate at {non_viable_percent:.1f}% — above watch threshold of '
            f'{thresholds["nonViable"]["watch"]}%'))

    desired_titles = {title for _, title, _ in desired}

    # ── Build a single batch for all creates + resolves ──────────────
    batch = db.batch()
    ops   = 0

    for severity, title, description in desired:
        if title not in open_by_title:
            new_ref = db.collection('monitoring_alerts').document()
            batch.set(new_ref, {
                'blockId':      block_id,
                'userId':       user_id,
                'severity':     severity,
                'title':        title,
                'description':  description,
                'method':       'Automated Threshold Check',
                'operator':     'System Auto-Flag',
                'resolved':     False,
                'detectedDate': _fs.SERVER_TIMESTAMP,
            })
            ops += 1
            print(f"   🚨 Creating {severity.upper()} alert: {title}")

    for title, ref in open_by_title.items():
        if title not in desired_titles:
            batch.update(ref, {
                'resolved':     True,
                'resolvedDate': _fs.SERVER_TIMESTAMP,
            })
            ops += 1
            print(f"   ✅ Auto-resolving: {title}")

    if ops > 0:
        batch.commit()
        print(f"   📝 Committed {ops} alert operation(s) in one batch")
    else:
        print("   ✓ No alert changes needed")


class PineappleDetector:
    """
    Real-time pineapple detection with duplicate prevention.
    Uses YOLOv5 for detection and DeepSORT for tracking.
    """
    
    def __init__(self, model_path: str, confidence_threshold: float = 0.5):
        """
        Initialize detector with YOLO model.
        
        Args:
            model_path: Path to your best.pt model file
            confidence_threshold: Minimum confidence for detections (0.0-1.0)
        """
        self.model_path = model_path
        self.confidence_threshold = confidence_threshold
        
        # Load YOLO model
        print(f"📦 Loading YOLO model from {model_path}...")
        try:
            # Try using ultralytics YOLO (newer, more stable)
            from ultralytics import YOLO
            self.model = YOLO(model_path)
            self.model.conf = confidence_threshold
            self.use_ultralytics = True
            print(f"✅ YOLO model loaded successfully (using Ultralytics)")
        except Exception as e:
            # Fallback to torch.hub (older method)
            print(f"⚠️ Ultralytics failed ({e}), using torch.hub...")
            self.model = torch.hub.load('ultralytics/yolov5', 'custom', path=model_path, force_reload=True, trust_repo=True)
            self.model.conf = confidence_threshold
            self.use_ultralytics = False
            print(f"✅ YOLO model loaded successfully (using torch.hub)")
        
        # Initialize DeepSORT tracker
        print(f"🔄 Initializing DeepSORT tracker...")
        self.tracker = DeepSort(
            max_age=30,           # Keep track for 30 frames without detection
            n_init=3,             # Confirm track after 3 consecutive detections
            max_iou_distance=0.7  # IoU threshold for matching
        )
        print(f"✅ DeepSORT tracker initialized")
        
        # Track unique pineapple IDs (prevents duplicates!)
        self.unique_ids: Dict[str, Set[int]] = {
            'bearing': set(),
            'non_bearing': set(),
            'non_viable': set()
        }
        
        # Detection statistics
        self.total_frames_processed = 0
        self.detection_active = False
        self.detection_thread = None
        
    def reset_tracking(self):
        """Reset all tracking data for a new scan"""
        self.unique_ids = {
            'bearing': set(),
            'non_bearing': set(),
            'non_viable': set()
        }
        self.total_frames_processed = 0
        print("🔄 Tracking data reset")
    
    def detect_frame(self, frame: np.ndarray) -> Dict:
        """
        Run detection on a single frame.
        
        Args:
            frame: Video frame as numpy array (BGR format)
        
        Returns:
            Dictionary with detection results and counts
        """
        # Run YOLO detection
        results = self.model(frame, verbose=False)
        
        # Prepare detections for DeepSORT
        detections_list = []
        
        if self.use_ultralytics:
            # Ultralytics YOLO format
            for result in results:
                boxes = result.boxes
                for box in boxes:
                    # Get bounding box coordinates
                    x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
                    bbox = [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]  # [x, y, width, height]
                    
                    # Get confidence and class
                    confidence = float(box.conf[0])
                    class_id = int(box.cls[0])
                    class_name = result.names[class_id]
                    
                    detections_list.append((bbox, confidence, class_name))
        else:
            # torch.hub format (fallback)
            detections_df = results.pandas().xyxy[0]
            for idx, row in detections_df.iterrows():
                bbox = [
                    row['xmin'],
                    row['ymin'],
                    row['xmax'] - row['xmin'],  # width
                    row['ymax'] - row['ymin']   # height
                ]
                confidence = row['confidence']
                class_name = row['name']
                
                detections_list.append((bbox, confidence, class_name))
        
        # Update tracks (assigns unique IDs!)
        tracks = self.tracker.update_tracks(detections_list, frame=frame)
        
        # Count only confirmed unique tracks
        new_detections = 0
        for track in tracks:
            if not track.is_confirmed():
                continue
            
            track_id = track.track_id
            class_name = track.det_class
            
            # Normalize class name
            if class_name in ['bearing', 'Bearing']:
                category = 'bearing'
            elif class_name in ['non-bearing', 'non_bearing', 'Non-Bearing', 'nonbearing']:
                category = 'non_bearing'
            elif class_name in ['non-viable', 'non_viable', 'Non-Viable', 'nonviable', 'discolored']:
                category = 'non_viable'
            else:
                print(f"⚠️ Unknown class: {class_name}")
                continue
            
            # Add to unique set (automatically prevents duplicates!)
            if track_id not in self.unique_ids[category]:
                self.unique_ids[category].add(track_id)
                new_detections += 1
        
        # Calculate current counts
        bearing_count = len(self.unique_ids['bearing'])
        non_bearing_count = len(self.unique_ids['non_bearing'])
        non_viable_count = len(self.unique_ids['non_viable'])
        total_count = bearing_count + non_bearing_count + non_viable_count
        
        self.total_frames_processed += 1
        
        return {
            'bearing': bearing_count,
            'non_bearing': non_bearing_count,
            'non_viable': non_viable_count,
            'total': total_count,
            'new_detections': new_detections,
            'frame_number': self.total_frames_processed
        }
    
    def start_detection(
        self,
        hls_url: str,
        block_id: str,
        user_id: str,
        fps: int = 1,
        update_interval: float = 2.0
    ) -> Optional[str]:
        """
        Start real-time detection from HLS stream.

        Args:
            hls_url: HLS stream URL (e.g., http://localhost:8888/stream/index.m3u8)
            block_id: Firestore block document ID
            user_id: User ID for the scan session
            fps: Frames per second to process (default: 1)
            update_interval: Seconds between Firebase updates (default: 2.0)

        Returns:
            Scan session ID if successful, None otherwise
        """
        # Create scan session (Firebase app is already initialized by app.py)
        scan_id = create_scan_session(block_id, user_id)
        if not scan_id:
            print("❌ Failed to create scan session")
            return None

        # Reset tracking data
        self.reset_tracking()

        # Start detection in background thread
        self.detection_active = True
        self.detection_thread = threading.Thread(
            target=self._detection_loop,
            args=(hls_url, block_id, scan_id, user_id, fps, update_interval),
            daemon=True
        )
        self.detection_thread.start()
        
        print(f"✅ Detection started - Scan ID: {scan_id}")
        return scan_id
    
    def _detection_loop(
        self,
        hls_url: str,
        block_id: str,
        scan_id: str,
        user_id: str,
        fps: int,
        update_interval: float
    ):
        """
        Main detection loop (runs in background thread).
        """
        # Initialize stream capture
        stream = HLSStreamCapture(hls_url, fps=fps)
        
        if not stream.start():
            print("❌ Failed to start stream capture")
            self.detection_active = False
            return
        
        print(f"🎥 Stream capture started - Processing at {fps} FPS")
        
        last_update_time = 0
        
        try:
            while self.detection_active and stream.is_running():
                # Get next frame
                frame = stream.get_frame(timeout=5.0)
                
                if frame is None:
                    print("⚠️ No frame received, retrying...")
                    continue
                
                # Run detection on frame
                results = self.detect_frame(frame)
                
                # Check if it's time to update Firebase
                current_time = time.time()
                if current_time - last_update_time >= update_interval:
                    # Single batch write: updates blocks/{id} AND scans/{id}
                    # in one network round-trip instead of two.
                    update_detection_batch(
                        block_id=block_id,
                        scan_id=scan_id,
                        bearing_count=results['bearing'],
                        non_bearing_count=results['non_bearing'],
                        non_viable_count=results['non_viable'],
                        total_count=results['total']
                    )
                    last_update_time = current_time
                    
                    print(f"📊 Frame {results['frame_number']}: "
                          f"Total={results['total']} "
                          f"(B:{results['bearing']}, "
                          f"NB:{results['non_bearing']}, "
                          f"NV:{results['non_viable']}) "
                          f"[+{results['new_detections']} new]")
        
        except Exception as e:
            print(f"❌ Error in detection loop: {e}")
            import traceback
            traceback.print_exc()
        
        finally:
            # Stop stream capture
            stream.stop()
            print("🛑 Detection loop stopped")
    
    def stop_detection(self, block_id: str, scan_id: str, user_id: str = '') -> bool:
        """
        Stop detection and finalize scan session.

        Args:
            block_id: Firestore block document ID
            scan_id: Scan session ID
            user_id: Owner UID — forwarded to alert creation so every
                     monitoring_alert document gets a userId field.

        Returns:
            True if stopped successfully, False otherwise
        """
        if not self.detection_active:
            print("⚠️ Detection is not active")
            return False
        
        print("🛑 Stopping detection...")
        self.detection_active = False
        
        # Wait for detection thread to finish
        if self.detection_thread:
            self.detection_thread.join(timeout=5.0)
        
        # Get final counts
        bearing_count = len(self.unique_ids['bearing'])
        non_bearing_count = len(self.unique_ids['non_bearing'])
        non_viable_count = len(self.unique_ids['non_viable'])
        total_count = bearing_count + non_bearing_count + non_viable_count
        
        # Calculate percentages
        if total_count > 0:
            bearing_percent = (bearing_count / total_count) * 100
            non_bearing_percent = (non_bearing_count / total_count) * 100
            non_viable_percent = (non_viable_count / total_count) * 100
        else:
            bearing_percent = 0.0
            non_bearing_percent = 0.0
            non_viable_percent = 0.0
        
        # Complete scan session
        success = complete_scan_session(
            scan_id=scan_id,
            block_id=block_id,
            bearing_count=bearing_count,
            non_bearing_count=non_bearing_count,
            non_viable_count=non_viable_count,
            total_count=total_count
        )
        
        if success:
            print(f"✅ Scan completed successfully")
            print(f"📊 Final Results:")
            print(f"   Total Pineapples: {total_count}")
            if total_count > 0:
                print(f"   Bearing: {bearing_count} ({bearing_percent:.1f}%)")
                print(f"   Non-Bearing: {non_bearing_count} ({non_bearing_percent:.1f}%)")
                print(f"   Non-Viable: {non_viable_count} ({non_viable_percent:.1f}%)")
            print(f"   Unique IDs tracked: {len(self.unique_ids['bearing']) + len(self.unique_ids['non_bearing']) + len(self.unique_ids['non_viable'])}")
            
            # ✅ CHECK THRESHOLDS AND CREATE/RESOLVE ALERTS
            print("\n🔔 Checking alert thresholds...")
            try:
                check_thresholds_and_create_alerts(
                    block_id=block_id,
                    bearing_percent=bearing_percent,
                    non_bearing_percent=non_bearing_percent,
                    non_viable_percent=non_viable_percent,
                    user_id=user_id,
                )
            except Exception as e:
                print(f"⚠️ Error checking thresholds: {e}")
        
        return success


# Global detector instance
_detector: Optional[PineappleDetector] = None


def get_detector(model_path: str = None) -> PineappleDetector:
    """
    Get or create global detector instance.
    
    Args:
        model_path: Path to best.pt model (only needed on first call)
    
    Returns:
        PineappleDetector instance
    """
    global _detector
    
    if _detector is None:
        if model_path is None:
            # Default path
            model_path = Path(__file__).parent.parent / 'best.pt'
        
        _detector = PineappleDetector(str(model_path))
    
    return _detector


# CLI testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python detection.py <hls_url> [block_id] [user_id]")
        print("Example: python detection.py http://localhost:8888/live/index.m3u8 block_123 user_abc")
        sys.exit(1)
    
    hls_url = sys.argv[1]
    block_id = sys.argv[2] if len(sys.argv) > 2 else "test_block"
    user_id = sys.argv[3] if len(sys.argv) > 3 else "test_user"
    
    # Initialize detector
    detector = get_detector()
    
    print("\n🚀 Starting detection test...")
    print(f"   HLS URL: {hls_url}")
    print(f"   Block ID: {block_id}")
    print(f"   User ID: {user_id}")
    print("\n   Press Ctrl+C to stop...\n")
    
    # Start detection
    scan_id = detector.start_detection(hls_url, block_id, user_id, fps=1)
    
    if scan_id:
        try:
            # Keep running until Ctrl+C
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\n⚠️ Stopping detection...")
            detector.stop_detection(block_id, scan_id)
    else:
        print("❌ Failed to start detection")