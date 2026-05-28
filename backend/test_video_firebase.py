"""
Test video detection with automatic Firestore updates
This simulates a real drone scanning workflow
"""

import cv2
import time
import sys
from pathlib import Path

# Add parent folder (pinevision/) to Python path
backend_parent = Path(__file__).parent.parent
sys.path.insert(0, str(backend_parent))

# Import from drone_conn package
from backend.drone_conn.detection import PineappleDetector, check_thresholds_and_create_alerts
from backend.drone_conn.firebase_client import (
    initialize_firebase,
    create_scan_session,
    complete_scan_session,
    update_block_stats,
    update_scan_progress
)


def test_video_with_firebase(video_path, block_id, user_id):
    """
    Test detection with automatic Firestore updates
    
    Args:
        video_path: Path to .mp4 video file
        block_id: Firestore block document ID
        user_id: User ID for the scan
    """
    print("="*70)
    print("🎬 VIDEO DETECTION TEST WITH FIREBASE INTEGRATION")
    print("="*70)
    print(f"📹 Video: {video_path}")
    print(f"📦 Block ID: {block_id}")
    print(f"👤 User ID: {user_id}")
    print("="*70 + "\n")
    
    # Step 1: Initialize Firebase
    print("🔧 Step 1: Initializing Firebase...")
    initialize_firebase()
    print("✅ Firebase connected!\n")
    
    # Step 2: Create scan session in Firestore
    print("🔧 Step 2: Creating scan session in Firestore...")
    scan_id = create_scan_session(block_id, user_id)
    
    if not scan_id:
        print("❌ Failed to create scan session")
        return False
    
    print(f"✅ Scan session created: {scan_id}")
    print(f"   👉 Check Firestore 'scans' collection for document: {scan_id}\n")
    
    # Step 3: Initialize YOLO detector
    print("🔧 Step 3: Loading YOLO model...")
    project_root = Path(__file__).parent.parent
    model_path = project_root / "backend" / "best.pt"
    
    if not model_path.exists():
        print(f"❌ Model not found at: {model_path}")
        return False
    
    detector = PineappleDetector(str(model_path), confidence_threshold=0.5)
    detector.reset_tracking()
    print("✅ YOLO model loaded!\n")
    
    # Step 4: Open video file
    print("🔧 Step 4: Opening video file...")
    cap = cv2.VideoCapture(str(video_path))
    
    if not cap.isOpened():
        print(f"❌ Cannot open video: {video_path}")
        return False
    
    # Get video properties
    fps = int(cap.get(cv2.CAP_PROP_FPS))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duration = total_frames / fps if fps > 0 else 0
    
    print(f"✅ Video opened successfully!")
    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps}")
    print(f"   Total Frames: {total_frames}")
    print(f"   Duration: {duration:.1f} seconds\n")
    
    # Step 5: Process video with periodic Firestore updates
    print("🔧 Step 5: Processing video and updating Firestore...")
    print("="*70)
    
    frame_count = 0
    process_every_n_frames = 5  # Process every 5th frame
    update_firestore_every = 30  # Update Firestore every 30 frames
    last_firestore_update = 0
    
    start_time = time.time()
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                break  # End of video
            
            frame_count += 1
            
            # Process frame
            if frame_count % process_every_n_frames == 0:
                results = detector.detect_frame(frame)
                
                # Print progress
                progress = (frame_count / total_frames) * 100
                print(f"📊 Frame {frame_count}/{total_frames} ({progress:.1f}%) - "
                      f"Total: {results['total']} "
                      f"(B:{results['bearing']}, NB:{results['non_bearing']}, NV:{results['non_viable']}) "
                      f"[+{results['new_detections']} new]")
                
                # Update Firestore periodically
                if frame_count - last_firestore_update >= update_firestore_every:
                    print(f"   💾 Updating Firestore...")
                    
                    # Update block stats
                    update_block_stats(
                        block_id=block_id,
                        bearing_count=results['bearing'],
                        non_bearing_count=results['non_bearing'],
                        non_viable_count=results['non_viable'],
                        total_count=results['total']
                    )
                    
                    # Update scan progress
                    update_scan_progress(
                        scan_id=scan_id,
                        bearing_count=results['bearing'],
                        non_bearing_count=results['non_bearing'],
                        non_viable_count=results['non_viable'],
                        total_count=results['total']
                    )
                    
                    print(f"   ✅ Firestore updated!")
                    last_firestore_update = frame_count
    
    except KeyboardInterrupt:
        print("\n⚠️ Processing interrupted by user")
    
    finally:
        cap.release()
    
    processing_time = time.time() - start_time
    
    # Step 6: Finalize scan and check alerts
    print("\n" + "="*70)
    print("🔧 Step 6: Finalizing and uploading final results...")
    
    # Get final counts
    bearing_count = len(detector.unique_ids['bearing'])
    non_bearing_count = len(detector.unique_ids['non_bearing'])
    non_viable_count = len(detector.unique_ids['non_viable'])
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
    
    # Complete scan session in Firestore
    success = complete_scan_session(
        scan_id=scan_id,
        block_id=block_id,
        bearing_count=bearing_count,
        non_bearing_count=non_bearing_count,
        non_viable_count=non_viable_count,
        total_count=total_count
    )
    
    if success:
        print(f"✅ Scan completed: {scan_id}")
        print("="*70)
        
        # Check thresholds and create/resolve alerts
        print("\n🔔 Checking alert thresholds...")
        try:
            check_thresholds_and_create_alerts(
                block_id=block_id,
                bearing_percent=bearing_percent,
                non_bearing_percent=non_bearing_percent,
                non_viable_percent=non_viable_percent
            )
        except Exception as e:
            print(f"⚠️ Error checking thresholds: {e}")
            import traceback
            traceback.print_exc()
    else:
        print("❌ Failed to complete scan session")
    
    # Step 7: Display final results
    print("\n" + "="*70)
    print("🎉 TEST COMPLETED!")
    print("="*70)
    
    if success:
        print("✅ All data successfully saved to Firestore!\n")
        
        print("📊 FINAL DETECTION RESULTS:")
        print(f"   Total Pineapples: {total_count}")
        print(f"   🟢 Bearing:       {bearing_count} ({bearing_percent:.1f}%)")
        print(f"   🟡 Non-Bearing:   {non_bearing_count} ({non_bearing_percent:.1f}%)")
        print(f"   🔴 Non-Viable:    {non_viable_count} ({non_viable_percent:.1f}%)\n")
        
        print("📝 FIRESTORE UPDATES:")
        print(f"   ✅ Scan session: scans/{scan_id}")
        print(f"   ✅ Block updated: blocks/{block_id}\n")
        
        print("⏱️  PROCESSING INFO:")
        print(f"   Frames processed: {frame_count}")
        print(f"   Processing time: {processing_time:.1f} seconds")
        print(f"   Processing speed: {frame_count/processing_time:.1f} FPS\n")
        
        print("🔍 VERIFICATION STEPS:")
        print("   1. Open Firebase Console")
        print("   2. Go to Firestore Database")
        print(f"   3. Check 'scans' collection → {scan_id}")
        print(f"   4. Check 'blocks' collection → {block_id}")
        print("   5. Check 'monitoring_alerts' collection for new alerts")
        print("   6. Check your frontend (alerts.html)")
        
    else:
        print("❌ Failed to save final results to Firestore")
    
    print("="*70)
    
    return success


if __name__ == "__main__":
    import sys
    
    print("\n")
    
    # Check arguments
    if len(sys.argv) < 4:
        print("❌ Missing arguments!")
        print("\nUsage:")
        print("  python test_video_firebase.py <video_path> <block_id> <user_id>")
        print("\nExample:")
        print("  python test_video_firebase.py ../test_videos/test.mp4 abc123xyz user_456")
        print("\nHow to get your IDs:")
        print("  1. Block ID: Firebase Console → Firestore → 'blocks' → copy Document ID")
        print("  2. User ID: Firebase Console → Firestore → 'blocks' → copy 'userId' field")
        sys.exit(1)
    
    video_path = Path(sys.argv[1])
    block_id = sys.argv[2]
    user_id = sys.argv[3]
    
    # Validate video exists
    if not video_path.exists():
        print(f"❌ Video file not found: {video_path}")
        print(f"\nMake sure the file exists at: {video_path.absolute()}")
        sys.exit(1)
    
    # Run test
    success = test_video_with_firebase(video_path, block_id, user_id)
    
    if success:
        print("\n✅ TEST PASSED! Your system is working correctly! 🎉\n")
    else:
        print("\n❌ TEST FAILED! Check the errors above.\n")