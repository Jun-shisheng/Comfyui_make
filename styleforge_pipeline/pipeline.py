#!/usr/bin/env python
"""
StyleForge 24h 自动化创作流水线
用法:
  python pipeline.py --mode characters --hours 24
  python pipeline.py --mode scenes    --hours 8
  python pipeline.py --mode variants  --hours 12 --ref_image ./face_ref.png
  python pipeline.py --mode full      --hours 48

流程: 生成 → 评分 → 筛选 → 入库 → 循环
"""
import argparse
import json
import os
import sys
import time
import signal
import hashlib
import threading
from pathlib import Path
from datetime import datetime, timedelta

import yaml

# Add parent dir for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from styleforge_webui import queue_prompt, poll_until_done, get_all_output_images, get_image, load_config

from generators.prompt_engine import PromptEngine
from scoring.aesthetic import AestheticScorer
from scoring.diversity import DiversityChecker
from scoring.face_uniqueness import FaceChecker


class StyleForgePipeline:
    def __init__(self, config_path="config_pipeline.yaml"):
        with open(os.path.join(os.path.dirname(__file__), config_path), "r", encoding="utf-8") as f:
            self.cfg = yaml.safe_load(f)
        self.cfg_wf, self.env = load_config()

        self.output_dir = Path(self.cfg["pipeline"]["output_dir"])
        self.tiers = {"S": [], "A": [], "B": [], "C": []}
        self.stats = {"generated": 0, "passed": 0, "failed": 0, "start_time": None, "end_time": None}

        # Init subsystems
        self.prompt_engine = PromptEngine(self.cfg)
        self.aesthetic = AestheticScorer(self.cfg) if self.cfg["scoring"]["aesthetic"]["enabled"] else None
        self.diversity = DiversityChecker(self.cfg) if self.cfg["scoring"]["diversity"]["enabled"] else None
        self.face_checker = FaceChecker(self.cfg) if self.cfg["scoring"]["face_uniqueness"]["enabled"] else None

        self._running = False
        self._checkpoint_file = self.output_dir / "checkpoint.json"

    def _save_checkpoint(self):
        ckpt = {"tiers": self.tiers, "stats": self.stats, "last_update": datetime.now().isoformat()}
        self._checkpoint_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._checkpoint_file, "w") as f:
            json.dump(ckpt, f, indent=2, default=str)

    def _load_checkpoint(self):
        if self._checkpoint_file.exists():
            with open(self._checkpoint_file) as f:
                ckpt = json.load(f)
            self.tiers = ckpt.get("tiers", self.tiers)
            self.stats = ckpt.get("stats", self.stats)

    def _score_image(self, image_path, prompt, metadata):
        """综合评分: aesthetic + diversity + face + composition"""
        scores = {}
        details = {}

        if self.aesthetic:
            score, detail = self.aesthetic.score(image_path)
            scores["aesthetic"] = score
            details["aesthetic"] = detail

        if self.diversity:
            score, detail = self.diversity.check(image_path, self.tiers["S"] + self.tiers["A"])
            scores["diversity"] = score
            details["diversity"] = detail

        if self.face_checker:
            score, detail = self.face_checker.analyze(image_path)
            scores["face"] = score
            details["face"] = detail

        # Weighted total
        weights = {"aesthetic": 0.5, "diversity": 0.3, "face": 0.2}
        total = sum(scores.get(k, 0.5) * weights.get(k, 0) for k in weights)
        return total, scores, details

    def _classify_tier(self, total_score, face_unique):
        """Assign tier based on scores"""
        tier_config = self.cfg["output"]["tiers"]
        if total_score >= 0.85 and face_unique:
            return "S"
        elif total_score >= 0.75:
            return "A"
        elif total_score >= 0.60:
            return "B"
        return "C"

    def _build_workflow(self, prompt, negative, width, height, seed, mode="txt2img"):
        """Build API prompt for generation based on mode."""
        from styleforge_webui import build_txt2img_workflow
        return build_txt2img_workflow(prompt, negative, width, height, seed)

    def _generate_one(self, prompt, negative, width, height):
        """Single generation call. Returns (image_path, metadata) or (None, error)."""
        import random
        seed = random.randint(1, 2**31 - 1)

        wf = self._build_workflow(prompt, negative, width, height, seed)
        try:
            result = queue_prompt(wf)
            prompt_id = result["prompt_id"]
            entry = poll_until_done(prompt_id, max_wait=900)
            if entry is None:
                return None, "Timeout"

            all_imgs = get_all_output_images(entry)
            if not all_imgs:
                return None, "No output"

            img_data = get_image(all_imgs[0]["filename"],
                                all_imgs[0].get("subfolder", ""),
                                all_imgs[0].get("type", "output"))
            if not img_data:
                return None, "Download failed"

            # Save with hash-based name
            img_hash = hashlib.md5(img_data).hexdigest()[:12]
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{timestamp}_{img_hash}.png"

            tier_img_dir = self.output_dir / "images"
            tier_img_dir.mkdir(parents=True, exist_ok=True)
            img_path = tier_img_dir / filename
            with open(img_path, "wb") as f:
                f.write(img_data)

            meta = {"prompt_id": prompt_id, "seed": seed, "prompt": prompt,
                    "negative": negative, "width": width, "height": height,
                    "hash": img_hash, "timestamp": timestamp}
            return str(img_path), meta
        except Exception as e:
            return None, str(e)

    def run(self, mode="characters", hours=24, ref_image=None):
        """Main generation loop."""
        mode_cfg = self.cfg["modes"].get(mode, {})
        if not mode_cfg:
            print(f"[ERROR] Unknown mode: {mode}")
            return

        # Resume if enabled
        if self.cfg["pipeline"]["resume"]:
            self._load_checkpoint()
            print(f"[RESUME] Loaded checkpoint: {self.stats['generated']} generated, {self.stats['passed']} passed")

        width = mode_cfg.get("width", 1024)
        height = mode_cfg.get("height", 1024)
        batch_interval = mode_cfg.get("batch_interval", 30)
        neg = "bad quality, worst quality, blurry, distorted, ugly, deformed, watermark, text, lowres"

        end_time = datetime.now() + timedelta(hours=hours)
        self.stats["start_time"] = datetime.now().isoformat()
        self._running = True

        print(f"\n{'='*60}")
        print(f"  StyleForge Pipeline — {mode_cfg.get('description', mode)}")
        print(f"  Duration: {hours}h | Resolution: {width}x{height}")
        print(f"  End: {end_time.strftime('%Y-%m-%d %H:%M')}")
        print(f"  Scoring: {'ON' if self.aesthetic else 'OFF'}")
        print(f"{'='*60}\n")

        checkpoint_count = 0
        while self._running and datetime.now() < end_time:
            prompt = self.prompt_engine.next_prompt(mode)
            negative = self.prompt_engine.negative_prompt(mode)

            print(f"[{datetime.now().strftime('%H:%M:%S')}] Generating: {prompt[:80]}...")

            img_path, meta_or_error = self._generate_one(prompt, negative, width, height)
            self.stats["generated"] += 1

            if img_path is None:
                print(f"  [FAIL] {meta_or_error}")
                self.stats["failed"] += 1
                time.sleep(5)
                continue

            # Score
            if self.aesthetic or self.diversity or self.face_checker:
                total, scores, details = self._score_image(img_path, prompt, meta_or_error)
                face_unique = details.get("face", {}).get("is_unique", True)
                tier = self._classify_tier(total, face_unique)

                score_str = f"total={total:.2f} "
                if "aesthetic" in scores:
                    score_str += f"aes={scores['aesthetic']:.2f} "
                if "diversity" in scores:
                    score_str += f"div={scores['diversity']:.2f} "
                if "face" in scores:
                    score_str += f"face={scores['face']:.2f} "
                score_str += f"→ {tier}"
            else:
                total = 0.5
                tier = "B"
                score_str = "scoring disabled → B"

            # Classify and save
            if tier in ("S", "A", "B"):
                self.tiers[tier].append({"path": img_path, "meta": meta_or_error})
                self.stats["passed"] += 1
                # Copy to tier folder
                tier_dir = self.output_dir / "high_score" / tier
                tier_dir.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy(img_path, tier_dir / os.path.basename(img_path))
            else:
                self.stats["failed"] += 1

            print(f"  [{tier}] {score_str}")

            # Checkpoint
            checkpoint_count += 1
            if checkpoint_count >= self.cfg["pipeline"].get("checkpoint_interval", 10):
                self._save_checkpoint()
                checkpoint_count = 0
                self._print_stats()

            time.sleep(batch_interval)

        self.stats["end_time"] = datetime.now().isoformat()
        self._save_checkpoint()
        self._print_summary()

    def _print_stats(self):
        s = self.stats
        runtime = ""
        if s["start_time"]:
            elapsed = datetime.now() - datetime.fromisoformat(s["start_time"])
            runtime = f" | Runtime: {str(elapsed).split('.')[0]}"
        print(f"  [STATS] Generated: {s['generated']} | Passed: {s['passed']} | "
              f"Failed: {s['failed']} | S:{len(self.tiers['S'])} A:{len(self.tiers['A'])} "
              f"B:{len(self.tiers['B'])}{runtime}")

    def _print_summary(self):
        print(f"\n{'='*60}")
        print(f"  Pipeline Complete")
        print(f"  Generated: {self.stats['generated']} | Passed: {self.stats['passed']}")
        print(f"  S-tier: {len(self.tiers['S'])} | A-tier: {len(self.tiers['A'])} | B-tier: {len(self.tiers['B'])}")
        print(f"  Results: {self.output_dir / 'high_score'}")
        print(f"{'='*60}\n")

    def stop(self):
        self._running = False
        self._save_checkpoint()


def main():
    parser = argparse.ArgumentParser(description="StyleForge 24h Pipeline")
    parser.add_argument("--mode", default="characters", choices=["characters", "scenes", "variants", "full"],
                       help="生成模式")
    parser.add_argument("--hours", type=float, default=24, help="运行时长（小时）")
    parser.add_argument("--ref_image", default=None, help="参考图路径（variants 模式需要）")
    parser.add_argument("--config", default="config_pipeline.yaml", help="配置文件路径")
    args = parser.parse_args()

    pipeline = StyleForgePipeline(args.config)

    def handle_sigint(sig, frame):
        print("\n[STOP] Graceful shutdown...")
        pipeline.stop()

    signal.signal(signal.SIGINT, handle_sigint)

    if args.mode == "full":
        modes = ["characters", "scenes"]
        hours_per = args.hours / len(modes)
        for m in modes:
            print(f"\n>>> Running mode: {m} ({hours_per}h)")
            pipeline.run(mode=m, hours=hours_per, ref_image=args.ref_image)
    else:
        pipeline.run(mode=args.mode, hours=args.hours, ref_image=args.ref_image)


if __name__ == "__main__":
    main()
