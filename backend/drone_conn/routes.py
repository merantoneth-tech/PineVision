"""
Flask Blueprint: /api/drone/*
Exposes the drone stream connection and health-check endpoints.
"""

from flask import Blueprint, request, jsonify
from . import service
from .detection import get_detector

drone_bp = Blueprint('drone', __name__, url_prefix='/api/drone')


@drone_bp.route('/connect', methods=['POST'])
def connect():
    """
    POST /api/drone/connect
    Body: { "rtmp_url": "rtmp://HOST:PORT/PATH" }

    Validates the RTMP URL, queries MediaMTX to confirm the drone is live,
    and returns the HLS playback URL on success.
    """
    body    = request.get_json(silent=True) or {}
    rtmp_url = (body.get('rtmp_url') or '').strip()

    if not rtmp_url:
        return jsonify({
            'ok':      False,
            'error':   'missing_url',
            'message': 'rtmp_url is required in the request body.',
        }), 400

    result = service.connect(rtmp_url)
    return jsonify(result), 200 if result['ok'] else 400


@drone_bp.route('/status', methods=['GET'])
def status():
    """
    GET /api/drone/status?path=STREAM_PATH

    Returns whether MediaMTX reports the given path as ready (publisher active).
    Called periodically by the frontend to detect stream drops.
    """
    path_name = (request.args.get('path') or '').strip()

    if not path_name:
        return jsonify({
            'ok':      False,
            'error':   'missing_path',
            'message': 'path query parameter is required.',
        }), 400

    return jsonify(service.status(path_name)), 200

# ═══════════════════════════════════════════════════════════
# NEW DETECTION ENDPOINTS
# ═══════════════════════════════════════════════════════════

@drone_bp.route('/start-detection', methods=['POST'])
def start_detection():
    """
    POST /api/drone/start-detection
    Body: {
        "hls_url": "http://localhost:8888/stream/index.m3u8",
        "block_id": "Ka9QfsVyjfOJ4U7xIlxt",
        "user_id": "ojoNzJsvnecrRgt8mn7HBbajmYJ2",
        "fps": 1  // optional, default 1
    }

    Starts real-time YOLO detection with DeepSORT tracking.
    Returns scan session ID.
    """
    body = request.get_json(silent=True) or {}
    
    hls_url = (body.get('hls_url') or '').strip()
    block_id = (body.get('block_id') or '').strip()
    user_id = (body.get('user_id') or '').strip()
    fps = body.get('fps', 1)
    
    # Validation
    if not hls_url:
        return jsonify({
            'ok': False,
            'error': 'missing_hls_url',
            'message': 'hls_url is required'
        }), 400
    
    if not block_id:
        return jsonify({
            'ok': False,
            'error': 'missing_block_id',
            'message': 'block_id is required'
        }), 400
    
    if not user_id:
        return jsonify({
            'ok': False,
            'error': 'missing_user_id',
            'message': 'user_id is required'
        }), 400
    
    # Get detector instance
    detector = get_detector()
    
    # Start detection
    scan_id = detector.start_detection(
        hls_url=hls_url,
        block_id=block_id,
        user_id=user_id,
        fps=fps
    )
    
    if scan_id:
        return jsonify({
            'ok': True,
            'scan_id': scan_id,
            'message': 'Detection started successfully'
        }), 200
    else:
        return jsonify({
            'ok': False,
            'error': 'detection_failed',
            'message': 'Failed to start detection'
        }), 500


@drone_bp.route('/stop-detection', methods=['POST'])
def stop_detection():
    """
    POST /api/drone/stop-detection
    Body: {
        "block_id": "Ka9QfsVyjfOJ4U7xIlxt",
        "scan_id": "scan_abc123"
    }

    Stops detection and finalizes the scan session.
    """
    body = request.get_json(silent=True) or {}

    block_id = (body.get('block_id') or '').strip()
    scan_id  = (body.get('scan_id')  or '').strip()
    user_id  = (body.get('user_id')  or '').strip()

    if not block_id or not scan_id:
        return jsonify({
            'ok': False,
            'error': 'missing_parameters',
            'message': 'block_id and scan_id are required'
        }), 400

    # Get detector instance
    detector = get_detector()

    # Stop detection — pass user_id so created alerts get the userId field
    success = detector.stop_detection(block_id, scan_id, user_id=user_id)
    
    if success:
        return jsonify({
            'ok': True,
            'message': 'Detection stopped and scan completed'
        }), 200
    else:
        return jsonify({
            'ok': False,
            'error': 'stop_failed',
            'message': 'Failed to stop detection'
        }), 500