print("Testing imports...")

try:
    import torch
    print("✅ PyTorch:", torch.__version__)
except Exception as e:
    print("❌ PyTorch failed:", e)

try:
    import cv2
    print("✅ OpenCV:", cv2.__version__)
except Exception as e:
    print("❌ OpenCV failed:", e)

try:
    import firebase_admin
    print("✅ Firebase Admin SDK installed")
except Exception as e:
    print("❌ Firebase failed:", e)

try:
    from deep_sort_realtime.deepsort_tracker import DeepSort
    print("✅ DeepSORT installed")
except Exception as e:
    print("❌ DeepSORT failed:", e)

print("\n🎉 All core dependencies installed successfully!")