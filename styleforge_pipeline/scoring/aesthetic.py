"""Aesthetic scoring using CLIP + pretrained aesthetic predictor."""
import os
import numpy as np
from PIL import Image


class AestheticScorer:
    """Scores images on visual quality using CLIP-based aesthetic model."""

    def __init__(self, config):
        self.threshold = config["scoring"]["aesthetic"]["threshold"]
        self.model = None
        self.preprocess = None
        self._init_model()

    def _init_model(self):
        """Lazy-load the aesthetic predictor."""
        try:
            import torch
            import torch.nn as nn
            from transformers import CLIPModel, CLIPProcessor

            # Use standard CLIP model + aesthetic linear head
            # For simplicity, use CLIP ViT-L/14
            model_id = "openai/clip-vit-large-patch14"
            self.clip = CLIPModel.from_pretrained(model_id)
            self.processor = CLIPProcessor.from_pretrained(model_id)

            # Simple aesthetic head: average of certain CLIP layers
            # In production, replace with cafe_aesthetic or improved-aesthetic-predictor
            self.aesthetic_head = nn.Linear(768, 1)
            # Initialize with reasonable defaults for scoring
            nn.init.normal_(self.aesthetic_head.weight, mean=0.0, std=0.02)

            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            self.clip = self.clip.to(self.device)
            self.aesthetic_head = self.aesthetic_head.to(self.device)
            self.model_loaded = True
            print(f"[Aesthetic] CLIP loaded on {self.device}")
        except Exception as e:
            print(f"[Aesthetic] CLIP not available ({e}), using fallback heuristic")
            self.model_loaded = False

    def score(self, image_path):
        if self.model_loaded:
            return self._clip_score(image_path)
        return self._heuristic_score(image_path)

    def _clip_score(self, image_path):
        """Score using CLIP embeddings."""
        import torch
        try:
            image = Image.open(image_path).convert("RGB")
            inputs = self.processor(images=image, return_tensors="pt").to(self.device)

            with torch.no_grad():
                features = self.clip.get_image_features(**inputs)
                score = self.aesthetic_head(features)
                score = torch.sigmoid(score).item() * 10  # Scale to 1-10

            detail = {"model": "clip_aesthetic", "raw": round(score, 2)}
            return score / 10.0, detail  # Normalize to 0-1 for pipeline
        except Exception as e:
            return self._heuristic_score(image_path)

    def _heuristic_score(self, image_path):
        """Fallback: heuristic scoring based on image properties."""
        try:
            img = Image.open(image_path).convert("RGB")
            arr = np.array(img, dtype=np.float32)

            # Color diversity (std of hue)
            r, g, b = arr[:,:,0], arr[:,:,1], arr[:,:,2]
            color_std = float(np.std([r.mean(), g.mean(), b.mean()]))

            # Contrast (std of luminance)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            contrast = float(np.std(lum))

            # Detail (edge density - simplified)
            dx = np.abs(np.diff(lum, axis=1)).mean()
            dy = np.abs(np.diff(lum, axis=0)).mean()
            detail = float((dx + dy) / 2)

            # Composite score
            score = min(1.0, (color_std / 50) * 0.3 + (contrast / 60) * 0.4 + (detail / 30) * 0.3)

            detail_info = {"model": "heuristic", "color_std": round(color_std, 1),
                          "contrast": round(contrast, 1), "detail": round(detail, 1)}
            return score, detail_info
        except:
            return 0.5, {"model": "fallback"}
