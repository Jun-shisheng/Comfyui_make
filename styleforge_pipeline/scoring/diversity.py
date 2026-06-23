"""Diversity checker — prevents batch homogenization."""
import os
import hashlib
import numpy as np
from PIL import Image
from collections import deque


class DiversityChecker:
    """Checks if new images are too similar to existing top-tier results."""

    def __init__(self, config):
        self.min_distance = config["scoring"]["diversity"]["min_distance"]
        self.recent_hashes = deque(maxlen=200)  # Perceptual hash ring buffer

    def check(self, image_path, existing_top_images):
        """Returns (score, detail). Score 0 = duplicate, 1 = highly novel."""
        try:
            phash = self._perceptual_hash(image_path)
        except:
            return 0.5, {"error": "hash failed"}

        # Check against recent hashes
        min_dist = 1.0
        for existing_hash in self.recent_hashes:
            dist = self._hamming_distance(phash, existing_hash) / len(phash)
            min_dist = min(min_dist, dist)

        self.recent_hashes.append(phash)

        if min_dist < self.min_distance:
            return 0.0, {"min_distance": round(min_dist, 3), "duplicate": True}

        # Bonus for novelty
        if min_dist > 0.5:
            return 1.0, {"min_distance": round(min_dist, 3), "novel": True}

        return min_dist * 2, {"min_distance": round(min_dist, 3)}  # Scale to 0-1

    def _perceptual_hash(self, image_path):
        """Simplified perceptual hash using downscaled luminance."""
        img = Image.open(image_path).convert("L").resize((32, 32), Image.LANCZOS)
        arr = np.array(img, dtype=np.float32)
        avg = arr.mean()
        return arr > avg  # Boolean array -> hash bits

    def _hamming_distance(self, hash1, hash2):
        return np.sum(hash1 != hash2)
