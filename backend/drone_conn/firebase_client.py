"""
Firebase Admin SDK client for real-time detection updates.

KEY FIX: No longer calls firebase_admin.initialize_app() itself.
app.py already initializes the default Firebase app on server start.
This module simply obtains a client from the already-initialized app.
If run standalone (e.g. testing detection.py directly), it will
initialize using serviceAccountKey.json as a fallback.
"""

import os
import firebase_admin
from firebase_admin import credentials, firestore
from typing import Optional

_db = None


def get_firestore_client():
    """
    Return the Firestore client, reusing the app that app.py already
    initialized. If no app exists yet (standalone / test mode), initializes
    one using serviceAccountKey.json in the backend/ directory.

    Called by every helper below, so we only pay the initialization cost once.
    """
    global _db
    if _db is not None:
        return _db

    if firebase_admin._apps:
        # Normal path: app.py already ran firebase_admin.initialize_app()
        _db = firestore.client()
    else:
        # Standalone / test path: running detection.py directly without app.py
        key_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            'serviceAccountKey.json'
        )
        if not os.path.exists(key_path):
            raise FileNotFoundError(
                f"Firebase service account not found: {key_path}\n"
                "Download it from Firebase Console and place it in backend/."
            )
        cred = credentials.Certificate(key_path)
        firebase_admin.initialize_app(cred)
        _db = firestore.client()
        print("✅ Firebase initialized (standalone mode)")

    return _db


# ═══════════════════════════════════════════════════════════════════════
# OPTIMIZED: BATCH WRITE — replaces two separate round-trips with one
# ═══════════════════════════════════════════════════════════════════════

def update_detection_batch(
    block_id: str,
    scan_id: str,
    bearing_count: int,
    non_bearing_count: int,
    non_viable_count: int,
    total_count: int
) -> bool:
    """
    Update both block stats AND scan progress in a single Firestore batch
    commit. Replaces the previous pattern of two separate .update() calls
    (update_block_stats + update_scan_progress), halving the number of
    network round-trips during every detection cycle.
    """
    try:
        db = get_firestore_client()

        bearing_pct     = (bearing_count     / total_count * 100) if total_count > 0 else 0.0
        non_bearing_pct = (non_bearing_count / total_count * 100) if total_count > 0 else 0.0
        non_viable_pct  = (non_viable_count  / total_count * 100) if total_count > 0 else 0.0

        batch = db.batch()

        # Write 1 — block aggregate stats (drives frontend live view)
        block_ref = db.collection('blocks').document(block_id)
        batch.update(block_ref, {
            'bearingPercent':    round(bearing_pct,     1),
            'nonBearingPercent': round(non_bearing_pct, 1),
            'nonViable':         round(non_viable_pct,  1),
            'totalPineapples':   total_count,
            'lastUpdate':        firestore.SERVER_TIMESTAMP,
        })

        # Write 2 — active scan session record
        scan_ref = db.collection('scans').document(scan_id)
        batch.update(scan_ref, {
            'bearing':    bearing_count,
            'nonBearing': non_bearing_count,
            'nonViable':  non_viable_count,
            'total':      total_count,
            'lastUpdate': firestore.SERVER_TIMESTAMP,
        })

        batch.commit()
        return True

    except Exception as e:
        print(f"❌ Error in detection batch update: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════
# SCAN SESSION LIFECYCLE
# ═══════════════════════════════════════════════════════════════════════

def create_scan_session(block_id: str, user_id: str) -> Optional[str]:
    """Create a new scan session document. Returns the generated scan ID."""
    try:
        db = get_firestore_client()
        scan_ref = db.collection('scans').document()
        scan_ref.set({
            'blockId':    block_id,
            'userId':     user_id,
            'status':     'active',
            'startTime':  firestore.SERVER_TIMESTAMP,
            'bearing':    0,
            'nonBearing': 0,
            'nonViable':  0,
            'total':      0,
            'lastUpdate': firestore.SERVER_TIMESTAMP,
        })
        print(f"✅ Created scan session: {scan_ref.id}")
        return scan_ref.id
    except Exception as e:
        print(f"❌ Error creating scan session: {e}")
        return None


def complete_scan_session(
    scan_id: str,
    block_id: str,
    bearing_count: int,
    non_bearing_count: int,
    non_viable_count: int,
    total_count: int
) -> bool:
    """
    Mark the scan as completed and increment the block's totalScans counter.
    Uses a batch write so both documents update atomically.
    """
    try:
        db = get_firestore_client()

        bearing_pct     = (bearing_count     / total_count * 100) if total_count > 0 else 0.0
        non_bearing_pct = (non_bearing_count / total_count * 100) if total_count > 0 else 0.0
        non_viable_pct  = (non_viable_count  / total_count * 100) if total_count > 0 else 0.0

        batch = db.batch()

        scan_ref = db.collection('scans').document(scan_id)
        batch.update(scan_ref, {
            'status':             'completed',
            'endTime':            firestore.SERVER_TIMESTAMP,
            'bearing':            bearing_count,
            'nonBearing':         non_bearing_count,
            'nonViable':          non_viable_count,
            'total':              total_count,
            'bearingPercent':     round(bearing_pct,     1),
            'nonBearingPercent':  round(non_bearing_pct, 1),
            'nonViablePercent':   round(non_viable_pct,  1),
        })

        block_ref = db.collection('blocks').document(block_id)
        batch.update(block_ref, {
            'totalScans':  firestore.Increment(1),
            'lastScanned': firestore.SERVER_TIMESTAMP,
        })

        batch.commit()
        print(f"✅ Scan session completed: {scan_id}")
        return True

    except Exception as e:
        print(f"❌ Error completing scan session: {e}")
        return False


# ═══════════════════════════════════════════════════════════════════════
# LEGACY SINGLE-WRITE HELPERS (kept for backward compatibility)
# The detection loop now uses update_detection_batch() above instead.
# ═══════════════════════════════════════════════════════════════════════

def update_block_stats(
    block_id: str,
    bearing_count: int,
    non_bearing_count: int,
    non_viable_count: int,
    total_count: int
) -> bool:
    """Single-document block stats write. Prefer update_detection_batch()."""
    try:
        db = get_firestore_client()
        bearing_pct     = (bearing_count     / total_count * 100) if total_count > 0 else 0.0
        non_bearing_pct = (non_bearing_count / total_count * 100) if total_count > 0 else 0.0
        non_viable_pct  = (non_viable_count  / total_count * 100) if total_count > 0 else 0.0

        db.collection('blocks').document(block_id).update({
            'bearingPercent':    round(bearing_pct,     1),
            'nonBearingPercent': round(non_bearing_pct, 1),
            'nonViable':         round(non_viable_pct,  1),
            'totalPineapples':   total_count,
            'lastUpdate':        firestore.SERVER_TIMESTAMP,
        })
        return True
    except Exception as e:
        print(f"❌ Error updating block stats: {e}")
        return False


def update_scan_progress(
    scan_id: str,
    bearing_count: int,
    non_bearing_count: int,
    non_viable_count: int,
    total_count: int
) -> bool:
    """Single-document scan progress write. Prefer update_detection_batch()."""
    try:
        db = get_firestore_client()
        db.collection('scans').document(scan_id).update({
            'bearing':    bearing_count,
            'nonBearing': non_bearing_count,
            'nonViable':  non_viable_count,
            'total':      total_count,
            'lastUpdate': firestore.SERVER_TIMESTAMP,
        })
        return True
    except Exception as e:
        print(f"❌ Error updating scan progress: {e}")
        return False
