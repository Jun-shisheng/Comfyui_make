#!/usr/bin/env python
"""
角色定制造型系统 — 针对小说具体角色，多角度生成 + 评分 + 精选
用法:
  python character_design.py --name "精灵女剑圣" --species "精灵" --gender "女" --role "剑圣" \
      --features "金色长发, 翠绿眼眸, 修长尖耳, 冷峻面容" --views 5 --keep 3
"""
import argparse
import json
import os
import sys
import time
import shutil
import hashlib
from pathlib import Path
from datetime import datetime

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from styleforge_webui import queue_prompt, poll_until_done, get_all_output_images, get_image, load_config

from scoring.aesthetic import AestheticScorer
from scoring.diversity import DiversityChecker
from scoring.face_uniqueness import FaceChecker


# 多角度视图模板
VIEW_TEMPLATES = {
    "front": {
        "cn": "正面全身像, 正对镜头, 展示全身服装设计",
        "en": "full body front view, facing camera, showing full outfit design, symmetrical composition"
    },
    "three_quarter": {
        "cn": "四分之三侧面, 展示面部立体感和身体轮廓",
        "en": "three-quarter view, showing facial structure and body profile, dynamic angle"
    },
    "side": {
        "cn": "完整侧面, 展示侧脸轮廓和服装侧面细节",
        "en": "full side profile, showing silhouette, costume side details, elegant pose"
    },
    "back": {
        "cn": "背面视角, 展示发型背面和服装后背设计",
        "en": "back view, showing hair from behind, back of outfit, looking over shoulder"
    },
    "closeup": {
        "cn": "面部特写, 半身肖像, 展示五官细节和表情",
        "en": "close-up portrait, half body, detailed facial features, subtle expression, shallow depth of field"
    },
    "action": {
        "cn": "战斗动态姿势, 手持武器, 展现角色力量感",
        "en": "dynamic action pose, wielding weapon, showing character power, dramatic composition"
    },
    "casual": {
        "cn": "日常放松姿态, 展示角色另一面的性格",
        "en": "casual relaxed pose, showing character's other side, natural expression"
    },
    "low_angle": {
        "cn": "仰视角度, 展现角色的威严和气势",
        "en": "low angle shot, showing character's authority and presence, imposing composition"
    },
}

# 角色种族特征模板
SPECIES_TRAITS = {
    "精灵": {"cn": "修长尖耳, 超凡脱俗的气质, 纤细优雅的体态, 与自然融为一体的感觉",
              "en": "long pointed elf ears, ethereal otherworldly presence, slender elegant build, natural grace"},
    "人类": {"cn": "写实皮肤质感, 自然的面部比例",
              "en": "realistic skin texture, natural facial proportions"},
    "兽人": {"cn": "兽耳兽尾, 野性魅力, 矫健的身姿",
              "en": "animal ears and tail, wild charm, athletic build"},
    "矮人": {"cn": "敦实身材, 粗壮手臂, 浓密胡须",
              "en": "stout build, thick arms, magnificent beard"},
    "龙族": {"cn": "龙角龙尾, 鳞片点缀, 龙瞳, 强大气场",
              "en": "dragon horns and tail, scale accents, dragon eyes, powerful aura"},
    "魔族": {"cn": "暗色角, 异色瞳孔, 神秘的魔纹, 魅惑与危险并存",
              "en": "dark horns, heterochromatic eyes, mysterious markings, seductive yet dangerous"},
}

# 职业/角色类型特征
ROLE_TRAITS = {
    "剑圣": {"cn": "手持长剑, 剑术高手的从容, 目光锐利, 周身隐约剑气",
              "en": "wielding longsword, master swordsman composure, sharp gaze, subtle sword aura"},
    "魔法师": {"cn": "手持法杖, 魔法符文漂浮, 周身元素波动, 智慧的眼神",
               "en": "holding staff, floating runes, elemental energy, wise eyes"},
    "刺客": {"cn": "暗色紧身衣, 双持匕首, 隐匿气息, 敏捷的姿态",
              "en": "dark bodysuit, dual daggers, stealthy presence, agile stance"},
    "骑士": {"cn": "重甲, 盾牌, 圣光环绕, 坚毅表情",
              "en": "heavy armor, shield, holy light, resolute expression"},
    "弓箭手": {"cn": "手持长弓, 鹰眼般的锐利, 轻甲, 敏捷",
               "en": "holding longbow, hawk-like sharpness, light armor, agile"},
    "治疗师": {"cn": "柔和的光芒, 治愈法杖, 温柔微笑, 神圣气质",
               "en": "soft glow, healing staff, gentle smile, holy presence"},
}


class CharacterDesigner:
    def __init__(self):
        self.cfg, self.env = load_config()
        self.aesthetic = AestheticScorer({"scoring": {"aesthetic": {"threshold": 5.5}}})
        self.diversity = DiversityChecker({"scoring": {"diversity": {"min_distance": 0.15}}})
        self.face = FaceChecker({"scoring": {"face_uniqueness": {"symmetry_threshold": 0.95, "anti_ai_face": True}}})

    def design_character(self, name, species, gender, role, features, num_views, keep_top):
        """Main design workflow for a single character."""
        print(f"\n{'='*70}")
        print(f"  StyleForge Character Design")
        print(f"  {name} | {species}{gender}·{role}")
        print(f"  Features: {features}")
        print(f"  Views: {num_views} | Keep top: {keep_top}")
        print(f"{'='*70}\n")

        # Build character base prompt
        species_trait = SPECIES_TRAITS.get(species, SPECIES_TRAITS["人类"])
        role_trait = ROLE_TRAITS.get(role, ROLE_TRAITS["剑圣"])
        gender_str = "女性" if gender == "女" else "男性"
        gender_en = "1girl" if gender == "女" else "1boy"

        base_cn = f"{species}{gender_str}{role}, {features}"
        base_en = f"{gender_en}, {species} {role}, {species_trait['en']}, {role_trait['en']}"

        # Output directory
        output_root = Path("styleforge_pipeline") / "output" / "character_design" / name
        output_root.mkdir(parents=True, exist_ok=True)

        # Select view templates
        selected_views = list(VIEW_TEMPLATES.items())
        if num_views <= len(selected_views):
            import random
            selected_views = random.sample(selected_views, num_views)
        else:
            selected_views = selected_views * (num_views // len(selected_views) + 1)
            selected_views = selected_views[:num_views]

        all_results = []
        negative = ("bad quality, worst quality, blurry, distorted, deformed, ugly, "
                    "extra fingers, cloned face, generic AI face, doll-like, "
                    "watermark, text, signature, cropped, out of frame, bad anatomy")

        for i, (view_name, view_prompt) in enumerate(selected_views):
            print(f"[{i+1}/{len(selected_views)}] {view_name} ({view_prompt['cn']})")

            # Build view-specific prompt
            prompt = (f"{base_cn}, {species_trait['cn']}, {role_trait['cn']}, "
                     f"{view_prompt['cn']}, {base_en}, {view_prompt['en']}, "
                     f"masterpiece, best quality, concept art, character design sheet")

            # Generate 3 variants per view
            variants = []
            for v in range(3):
                import random as rnd
                seed = rnd.randint(1, 2**31 - 1)
                wf = self._build_workflow(prompt, negative, 1024, 1024, seed)

                try:
                    result = queue_prompt(wf)
                    entry = poll_until_done(result["prompt_id"], max_wait=600)
                    if entry is None:
                        print(f"    Variant {v+1}: Timeout")
                        continue

                    imgs = get_all_output_images(entry)
                    if not imgs:
                        print(f"    Variant {v+1}: No output")
                        continue

                    img_data = get_image(imgs[0]["filename"], imgs[0].get("subfolder", ""), imgs[0].get("type", "output"))
                    if not img_data:
                        print(f"    Variant {v+1}: Download failed")
                        continue

                    # Save variant
                    img_hash = hashlib.md5(img_data).hexdigest()[:8]
                    img_path = output_root / f"{view_name}_v{v+1}_{img_hash}.png"
                    with open(img_path, "wb") as f:
                        f.write(img_data)

                    # Score
                    aes_score, _ = self.aesthetic.score(str(img_path))
                    div_score, _ = self.diversity.check(str(img_path), [])
                    face_score, _ = self.face.analyze(str(img_path))
                    total = aes_score * 0.5 + div_score * 0.3 + face_score * 0.2

                    variants.append({
                        "path": str(img_path),
                        "view": view_name,
                        "variant": v + 1,
                        "seed": seed,
                        "scores": {"aes": round(aes_score, 3), "div": round(div_score, 3),
                                   "face": round(face_score, 3), "total": round(total, 3)}
                    })
                    print(f"    Variant {v+1}: total={total:.3f} (aes={aes_score:.3f})")

                except Exception as e:
                    print(f"    Variant {v+1}: Error - {e}")
                    continue

            all_results.extend(variants)

        # ======== Final selection ========
        print(f"\n{'='*70}")
        print(f"  Final Selection — keeping top {keep_top}")
        print(f"{'='*70}\n")

        # Sort by total score
        all_results.sort(key=lambda x: x["scores"]["total"], reverse=True)

        final_dir = output_root / "final_selection"
        final_dir.mkdir(exist_ok=True)

        kept = []
        # Ensure view diversity: keep at least 1 per unique view, then fill by score
        seen_views = set()
        for r in all_results:
            if len(kept) >= keep_top:
                break
            if r["view"] not in seen_views:
                seen_views.add(r["view"])
                kept.append(r)
                shutil.copy(r["path"], final_dir / f"TOP_{len(kept):02d}_{r['view']}.png")
                print(f"  #{len(kept)} [{r['view']}] total={r['scores']['total']:.3f} "
                      f"→ {final_dir}/TOP_{len(kept):02d}_{r['view']}.png")

        # Fill remaining slots by pure score
        for r in all_results:
            if len(kept) >= keep_top:
                break
            if r not in kept:
                kept.append(r)
                shutil.copy(r["path"], final_dir / f"TOP_{len(kept):02d}_{r['view']}.png")
                print(f"  #{len(kept)} [{r['view']}] total={r['scores']['total']:.3f} "
                      f"→ {final_dir}/TOP_{len(kept):02d}_{r['view']}.png")

        # Save report
        report = {
            "character": {"name": name, "species": species, "gender": gender,
                         "role": role, "features": features},
            "total_generated": len(all_results),
            "kept": [{"rank": i+1, "view": r["view"], "scores": r["scores"],
                      "path": f"TOP_{i+1:02d}_{r['view']}.png"} for i, r in enumerate(kept)],
            "all_results": [{"view": r["view"], "scores": r["scores"]} for r in all_results],
            "timestamp": datetime.now().isoformat()
        }
        with open(output_root / "design_report.json", "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

        print(f"\n  Design complete: {len(kept)} selected from {len(all_results)} generated")
        print(f"  Results: {final_dir}")
        print(f"  Report: {output_root / 'design_report.json'}\n")
        return report

    def _build_workflow(self, prompt, negative, width, height, seed):
        from styleforge_webui import build_txt2img_workflow
        return build_txt2img_workflow(prompt, negative, width, height, seed)


def main():
    parser = argparse.ArgumentParser(description="StyleForge Character Design")
    parser.add_argument("--name", required=True, help="角色名（如: 艾琳·风语者）")
    parser.add_argument("--species", required=True, help="种族（精灵/人类/兽人/矮人/龙族/魔族）")
    parser.add_argument("--gender", required=True, choices=["男", "女"], help="性别")
    parser.add_argument("--role", required=True, help="职业（剑圣/魔法师/刺客/骑士/弓箭手/治疗师）")
    parser.add_argument("--features", required=True, help="关键特征（如: 金色长发,翠绿眼眸,修长尖耳）")
    parser.add_argument("--views", type=int, default=5, help="视角数量（默认 5）")
    parser.add_argument("--keep", type=int, default=3, help="最终保留数量（默认 3）")
    args = parser.parse_args()

    designer = CharacterDesigner()
    designer.design_character(
        name=args.name, species=args.species, gender=args.gender,
        role=args.role, features=args.features, num_views=args.views, keep_top=args.keep
    )


if __name__ == "__main__":
    main()
