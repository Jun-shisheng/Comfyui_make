#!/usr/bin/env python
"""
角色批量生成器 — 读取 character_factory 的 JSON，逐个跑 character_design
用法:
  python character_batch.py --from character_concepts.json --hours 24
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime


def main():
    parser = argparse.ArgumentParser(description="批量角色定制造型")
    parser.add_argument("--from", dest="from_file", required=True, help="character_factory 输出的 JSON 文件")
    parser.add_argument("--hours", type=float, default=24, help="总运行时长")
    parser.add_argument("--views", type=int, default=5, help="每个角色视角数")
    parser.add_argument("--keep", type=int, default=3, help="每个角色保留数")
    args = parser.parse_args()

    # Load characters
    json_path = Path("styleforge_pipeline/output") / args.from_file
    if not json_path.exists():
        print(f"[ERROR] File not found: {json_path}")
        sys.exit(1)

    with open(json_path, encoding="utf-8") as f:
        data = json.load(f)
    characters = data.get("characters", [])

    print(f"\n{'='*70}")
    print(f"  Character Batch Runner")
    print(f"  Characters: {len(characters)} | Views each: {args.views}")
    print(f"  Duration: {args.hours}h | Keep: {args.keep} per character")
    print(f"{'='*70}\n")

    end_time = datetime.now() + datetime.timedelta(hours=args.hours)
    completed = 0
    failed = 0

    for i, c in enumerate(characters):
        if datetime.now() >= end_time:
            print(f"\n  Time's up! Completed {completed}/{len(characters)} characters.")
            break

        name = c["name"]
        race = c["race"]
        gender = c["gender"]
        cls_name = c["class"]
        features = f"{c['hair']}长发, {c['eyes']}眼眸, {c['build']}, {', '.join(c['traits'][:2])}, {c['personality_trait']}"

        print(f"\n--- [{i+1}/{len(characters)}] {name} ({race}·{cls_name}) ---")
        print(f"    Features: {features[:100]}...")

        cmd = [
            sys.executable,
            "styleforge_pipeline/character_design.py",
            "--name", name,
            "--species", race if race in ("精灵", "人类", "龙族", "兽人", "魔族", "矮人") else "人类",
            "--gender", "女" if gender == "女" else "男",
            "--role", cls_name if cls_name in ("剑圣", "魔法师", "刺客", "骑士", "弓箭手", "治疗师") else "剑圣",
            "--features", features,
            "--views", str(args.views),
            "--keep", str(args.keep),
        ]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
            if result.returncode == 0:
                completed += 1
                print(f"    [OK] Completed")
            else:
                failed += 1
                print(f"    [FAIL] {result.stderr[:200] if result.stderr else 'Unknown error'}")
        except subprocess.TimeoutExpired:
            failed += 1
            print(f"    [TIMEOUT] > 30 min")
        except Exception as e:
            failed += 1
            print(f"    [ERROR] {e}")

        print(f"    Progress: {completed} done, {failed} failed, "
              f"{len(characters) - i - 1} remaining")

    print(f"\n{'='*70}")
    print(f"  Batch Complete: {completed} success, {failed} failed")
    print(f"  Results: styleforge_pipeline/output/character_design/")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    main()
