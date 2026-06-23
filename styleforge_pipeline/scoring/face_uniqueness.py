"""Face uniqueness checker — detects and penalizes generic 'AI face' patterns."""
import os
import numpy as np
from PIL import Image
from collections import deque


class FaceChecker:
    """Analyzes facial characteristics for uniqueness and anti-AI-face detection."""

    def __init__(self, config):
        self.cfg = config["scoring"]["face_uniqueness"]
        self.symmetry_threshold = self.cfg.get("symmetry_threshold", 0.95)
        self.anti_ai_face = self.cfg.get("anti_ai_face", True)
        self._face_history = deque(maxlen=500)
        self._face_detector_loaded = False
        self._init_face_detector()

    def _init_face_detector(self):
        """Try to load a face detection model."""
        try:
            import cv2
            cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            if os.path.exists(cascade_path):
                self.face_cascade = cv2.CascadeClassifier(cascade_path)
                self._face_detector_loaded = True
        except ImportError:
            pass

    def analyze(self, image_path):
        """Returns (score, detail). Score 0 = generic AI face, 1 = unique character."""
        try:
            img = Image.open(image_path).convert("RGB")
            arr = np.array(img)
            h, w = arr.shape[:2]
        except:
            return 0.5, {"error": "cannot open image"}

        score = 0.5
        detail = {}

        # 1. Symmetry check (AI faces tend to be too symmetric)
        if self.anti_ai_face:
            sym_score, sym_detail = self._check_symmetry(arr)
            detail["symmetry"] = sym_detail
            score += (sym_score - 0.5) * 0.4

        # 2. Color variance in skin tones (AI faces tend to have too-uniform skin)
        if self.anti_ai_face:
            skin_score, skin_detail = self._check_skin_variance(arr)
            detail["skin_variance"] = skin_detail
            score += (skin_score - 0.5) * 0.3

        # 3. Face detection + embedding diversity
        if self._face_detector_loaded:
            face_score, face_detail = self._check_face_diversity(arr)
            detail["face_diversity"] = face_detail
            score += (face_score - 0.5) * 0.3

        # Clip
        score = max(0.0, min(1.0, score))
        detail["is_unique"] = score > 0.5

        return score, detail

    def _check_symmetry(self, arr):
        """Check facial symmetry. 1.0 = perfectly symmetric (bad), 0.0 = asymmetric (good)."""
        h, w = arr.shape[:2]
        # Compare left and right halves
        left = arr[:, :w//2].astype(np.float32)
        right = np.fliplr(arr[:, w//2:].astype(np.float32))

        if left.shape[1] != right.shape[1]:
            min_w = min(left.shape[1], right.shape[1])
            left, right = left[:, :min_w], right[:, :min_w]

        diff = np.abs(left - right).mean() / 255.0
        # Higher diff = more asymmetric = better
        symmetry_score = min(1.0, diff * 10)
        return symmetry_score, {"asymmetry": round(diff, 4)}

    def _check_skin_variance(self, arr):
        """Check skin tone variance. More variance = more natural."""
        # Sample center of image (where face likely is)
        h, w = arr.shape[:2]
        center = arr[h//4:3*h//4, w//4:3*w//4]

        # Compute per-channel std dev
        stds = [float(np.std(center[:,:,c])) for c in range(3)]
        avg_std = np.mean(stds)

        # Higher std = more texture detail = better
        skin_score = min(1.0, avg_std / 30.0)
        return skin_score, {"texture_std": round(avg_std, 1)}

    def _check_face_diversity(self, arr):
        """Use Haar cascade to find faces and check if they look unique."""
        try:
            gray = np.array(Image.fromarray(arr).convert("L"))
            faces = self.face_cascade.detectMultiScale(gray, 1.1, 5)

            if len(faces) == 0:
                return 0.5, {"faces_detected": 0}

            # Extract first face region and compute simple embedding
            x, y, fw, fh = faces[0]
            face_region = gray[y:y+fh, x:x+fw]
            face_region = np.array(Image.fromarray(face_region).resize((64, 64)))
            face_vec = face_region.flatten().astype(np.float32) / 255.0

            # Check against history
            min_dist = 1.0
            for hist_vec in self._face_history:
                dist = np.linalg.norm(face_vec - hist_vec) / np.sqrt(len(face_vec))
                min_dist = min(min_dist, dist)

            self._face_history.append(face_vec)
            face_score = min(1.0, min_dist * 5)
            return face_score, {"faces": len(faces), "min_face_distance": round(min_dist, 3)}
        except:
            return 0.5, {"error": "face_detect_failed"}
