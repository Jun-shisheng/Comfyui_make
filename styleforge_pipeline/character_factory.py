#!/usr/bin/env python
"""
角色工厂 — 自动创作独特的角色概念并生成设定图
用法:
  python character_factory.py --count 10          # 自动创建 10 个角色
  python character_factory.py --race 精灵 --count 5  # 只生成精灵族
  python character_factory.py --mode batch --count 100 --hours 24  # 批量模式
"""
import argparse
import json
import os
import sys
import random
import time
import subprocess
from pathlib import Path
from datetime import datetime
from itertools import product

# ============================================================
# 角色要素库 — 所有可组合的角色元素
# ============================================================

RACES = {
    "精灵": {
        "subtypes": ["高等精灵", "木精灵", "暗夜精灵", "月精灵", "星精灵", "血精灵"],
        "traits": ["修长尖耳", "超凡脱俗的气质", "与自然共鸣", "百年智慧的眼神",
                  "月光下泛微光", "动作如流水般优雅", "对魔法敏感", "长寿者的从容"],
        "hair_colors": ["银白色", "淡金色", "月光银", "琥珀色", "深翠绿", "紫罗兰"],
        "eye_colors": ["翠绿", "琥珀金", "银灰", "深海蓝", "紫晶"],
        "build": ["纤细修长", "优雅轻盈", "高挑矫健"],
    },
    "人类": {
        "subtypes": ["北方人", "南方人", "东方人", "西方人", "游牧民族", "海岛居民"],
        "traits": ["坚韧不拔", "适应力强", "充满生命力", "雄心壮志",
                  "平凡的伟大", "工匠精神", "冒险者的好奇心"],
        "hair_colors": ["黑色", "棕色", "金色", "红色", "银灰", "深褐"],
        "eye_colors": ["深棕", "琥珀", "灰蓝", "翠绿", "深灰"],
        "build": ["健壮", "匀称", "精瘦", "魁梧"],
    },
    "龙族": {
        "subtypes": ["炎龙", "冰龙", "雷龙", "光龙", "暗龙", "虚空龙"],
        "traits": ["龙角弯曲", "竖瞳威严", "鳞片点缀肌肤", "压倒性的气场",
                  "古老血脉的骄傲", "龙威", "尾部鳞甲", "半龙化特征可控"],
        "hair_colors": ["深红如焰", "冰蓝", "银白", "漆黑", "紫黑渐变"],
        "eye_colors": ["金色竖瞳", "赤红", "冰蓝", "紫金异色"],
        "build": ["修长而有力", "肌肉与优雅并存", "威慑性体态"],
    },
    "兽人": {
        "subtypes": ["狼族", "猫族", "狐族", "熊族", "鹰族", "蛇族"],
        "traits": ["兽耳灵动", "尾巴自然摆动", "野性魅力", "敏锐的动物直觉",
                  "矫健的身手", "忠诚的部族精神", "原始的感官"],
        "hair_colors": ["银灰", "棕褐", "纯白", "斑纹", "火红", "深黑"],
        "eye_colors": ["金色兽瞳", "琥珀", "翠绿", "冰蓝", "赤红"],
        "build": ["矫健敏捷", "力量感十足", "完美平衡"],
    },
    "魔族": {
        "subtypes": ["魅魔", "影魔", "炎魔", "冰魔", "混沌魔族"],
        "traits": ["弯曲的角", "异色瞳孔", "神秘魔纹", "危险而迷人的气质",
                  "暗影追随", "若隐若现的魔气", "蛊惑人心的魅力"],
        "hair_colors": ["深紫", "暗红", "银白", "漆黑", "渐变蓝紫"],
        "eye_colors": ["血红", "紫金异瞳", "暗紫", "赤金"],
        "build": ["妖娆", "矫健", "威慑"],
    },
    "矮人": {
        "subtypes": ["山岳矮人", "熔炉矮人", "宝石矮人", "符文矮人"],
        "traits": ["敦实身材", "粗壮手臂", "浓密胡须", "火热的锻造之心",
                  "对宝石的敏锐嗅觉", "固执而忠诚", "豪爽大笑"],
        "hair_colors": ["火红", "深褐", "灰白", "金棕"],
        "eye_colors": ["深棕", "琥珀", "灰蓝", "墨绿"],
        "build": ["敦实强壮", "粗犷有力", "宽厚稳重"],
    },
    "天使": {
        "subtypes": ["炽天使", "智天使", "座天使", "权天使", "能天使"],
        "traits": ["圣洁羽翼", "光环璀璨", "神圣不容亵渎", "慈悲的眼神",
                  "光明之力", "古老的誓言", "翅膀上的圣痕"],
        "hair_colors": ["纯白", "淡金", "银白", "白金渐变"],
        "eye_colors": ["天蓝", "纯金", "银白", "淡紫"],
        "build": ["庄严挺拔", "轻盈飘逸", "神圣威压"],
    },
}

CLASSES = {
    "剑圣": {"weapon": "长剑/太刀", "style": "剑术宗师, 极致武艺, 剑芒如虹", "armor": "轻甲或布衣, 注重灵活"},
    "魔法师": {"weapon": "法杖/魔导书", "style": "元素环绕, 魔力涌动, 智慧深邃", "armor": "法袍, 符文装饰"},
    "刺客": {"weapon": "双匕首/短刃", "style": "暗影潜行, 一击致命, 敏捷如风", "armor": "紧身暗色皮甲"},
    "骑士": {"weapon": "长剑/盾牌/骑枪", "style": "荣耀守护, 钢铁意志, 圣光加护", "armor": "重甲, 铠甲华丽"},
    "弓箭手": {"weapon": "长弓/弩", "style": "百步穿杨, 鹰眼锐利, 疾风之矢", "armor": "轻甲, 便于行动"},
    "治疗师": {"weapon": "治愈法杖/圣典", "style": "温柔坚定, 生命之光, 慈悲之心", "armor": "圣袍, 纯净素雅"},
    "召唤师": {"weapon": "召唤契约/魔导器", "style": "与异界沟通, 万兽臣服, 精神力", "armor": "神秘风格的袍服"},
    "武僧": {"weapon": "拳套/棍棒/徒手", "style": "内功深厚, 气劲外放, 刚柔并济", "armor": "简朴布衣, 念珠装饰"},
    "符文师": {"weapon": "符文刻印/符文锤", "style": "符文流转, 铭刻万物, 古老传承", "armor": "符文镶嵌的装束"},
    "龙骑士": {"weapon": "龙枪/龙牙刃", "style": "与龙共舞, 天空霸主, 龙息", "armor": "龙鳞甲, 龙翼披风"},
}

PERSONALITIES = {
    "冷静睿智": ["理性的目光", "深思熟虑的表情", "沉稳的站姿"],
    "热血冲动": ["燃烧的斗志", "不羁的笑容", "充满爆发力的姿态"],
    "冷酷孤傲": ["冷冽的眼神", "高傲的下巴", "疏离的气质"],
    "温柔内敛": ["柔和的微笑", "平静如水的眼神", "优雅的举止"],
    "邪魅狂狷": ["危险的笑意", "挑衅的眼神", "狂放不羁"],
    "忠厚坚毅": ["坚毅的目光", "可靠的背影", "如山般的沉稳"],
}

ART_STYLES = {
    "二次元": "anime style, cel shaded, vibrant colors, clean linework, Japanese anime aesthetic",
    "半写实": "semi-realistic, digital painting, soft shading, character concept art",
    "暗黑幻想": "dark fantasy, gritty realism, dramatic lighting, Elden Ring inspired",
    "韩系": "Korean manhwa style, polished rendering, glamorous, intricate details",
    "新海诚": "Makoto Shinkai style, soft lighting, ethereal atmosphere, detailed backgrounds",
    "最终幻想": "Final Fantasy concept art, detailed costume design, cinematic rendering",
    "原神系": "Genshin Impact style, vibrant colors, elemental effects, anime game aesthetic",
    "厚涂油画": "oil painting style, thick brushstrokes, classical composition, dramatic chiaroscuro",
}

QUALIFIERS = [
    "独特的面部特征, 拒绝千篇一律的网红脸",
    "有个性的五官比例, 非对称的自然美感",
    "真实的皮肤质感, 不是塑料般的AI皮肤",
    "有辨识度的面容, 让人过目不忘",
    "自然的瑕疵增添了真实感",
    "气质独特, 不是量产型美人",
]


class CharacterFactory:
    def __init__(self):
        self._used_combos = set()
        self._characters = []

    def create_character(self, race=None, cls=None):
        """Create a unique character concept from the element library."""
        # Select race
        if race and race in RACES:
            race_name = race
        else:
            race_name = random.choice(list(RACES.keys()))
        race_data = RACES[race_name]

        # Select class
        if cls and cls in CLASSES:
            class_name = cls
        else:
            class_name = random.choice(list(CLASSES.keys()))
        class_data = CLASSES[class_name]

        # Select subtype
        subtype = random.choice(race_data["subtypes"])

        # Select gender
        gender = random.choice(["女", "男"])
        gender_en = "1girl" if gender == "女" else "1boy"
        gender_cn = "女性" if gender == "女" else "男性"

        # Select physical traits
        hair = random.choice(race_data["hair_colors"])
        eyes = random.choice(race_data["eye_colors"])
        build = random.choice(race_data["build"])
        traits = random.sample(race_data["traits"], min(3, len(race_data["traits"])))

        # Select personality
        pers_name = random.choice(list(PERSONALITIES.keys()))
        pers_traits = random.choice(PERSONALITIES[pers_name])

        # Select art style
        style_name = random.choice(list(ART_STYLES.keys()))
        style_desc = ART_STYLES[style_name]

        # Select qualifier
        qualifier = random.choice(QUALIFIERS)

        # Generate name
        name = self._generate_name(race_name, gender)

        # Build concept
        concept = {
            "name": name,
            "race": race_name,
            "subtype": subtype,
            "gender": gender,
            "class": class_name,
            "hair": hair,
            "eyes": eyes,
            "build": build,
            "traits": traits,
            "personality": pers_name,
            "personality_trait": pers_traits,
            "art_style": style_name,
            "art_style_desc": style_desc,
            "qualifier": qualifier,
        }

        # Generate prompt
        concept["prompt"] = self._build_prompt(concept, gender_en, gender_cn)
        concept["negative"] = self._build_negative()

        return concept

    def _generate_name(self, race, gender):
        """Generate a fitting name based on race and gender."""
        name_parts = {
            "精灵": {
                "prefix": ["艾", "莉", "瑟", "伊", "洛", "菲", "诺", "琳"],
                "suffix": ["琳", "娅", "尔", "娜", "迪斯", "温", "瑞尔", "露恩"],
            },
            "人类": {
                "prefix": ["亚", "艾", "卡", "雷", "玛", "赛", "维", "奥"],
                "suffix": ["里克", "琳", "尔", "娜", "特", "莉亚", "修斯", "德"],
            },
            "龙族": {
                "prefix": ["炎", "冰", "雷", "暗", "光", "虚空", "龙", "焰"],
                "suffix": ["之翼", "牙", "鳞", "焰", "啸", "帝", "皇", "君"],
            },
            "兽人": {
                "prefix": ["狼", "猫", "狐", "熊", "鹰", "蛇", "爪", "牙"],
                "suffix": ["行者", "猎手", "之影", "咆哮", "锐眼", "轻语", "风暴", "疾风"],
            },
            "魔族": {
                "prefix": ["暗", "魅", "影", "炎", "冰", "血", "混沌", "虚"],
                "suffix": ["女王", "领主", "魅影", "之触", "低语", "君王", "使者", "收割者"],
            },
            "矮人": {
                "prefix": ["铁", "石", "火", "金", "锤", "钢", "山", "炉"],
                "suffix": ["之锤", "铁匠", "矿主", "宝石", "烈酒", "锻炉", "岩心", "熔火"],
            },
            "天使": {
                "prefix": ["圣", "光", "羽", "辉", "明", "净", "炽", "辉"],
                "suffix": ["之翼", "天使", "之光", "使者", "守护", "颂歌", "圣裁", "降临"],
            },
        }
        parts = name_parts.get(race, name_parts["人类"])
        # Generate 2-syllable name
        if race in ("龙族", "魔族", "矮人"):
            return random.choice(parts["prefix"]) + random.choice(parts["suffix"])
        else:
            p1 = random.choice(parts["prefix"])
            p2 = random.choice(parts["suffix"])
            sep = "" if random.random() > 0.5 else "·"
            return f"{p1}{sep}{p2}"

    def _build_prompt(self, c, gender_en, gender_cn):
        templates = [
            # 角色设定图风格
            (f"character design sheet, {gender_en}, {c['race']} {c['subtype']} {c['class']}, "
             f"{c['art_style_desc']}, "
             f"{c['hair']}长发, {c['eyes']}眼眸, {c['build']}体型, "
             f"{', '.join(c['traits'][:2])}, "
             f"full body front view, reference sheet, concept art, "
             f"{c['qualifier']}, masterpiece, high quality"),

            # 场景中的角色
            (f"{gender_cn}{c['race']}{c['subtype']}{c['class']}, "
             f"{c['hair']}长发飘逸, {c['eyes']}眼眸闪光, "
             f"{c['personality_trait']}, "
             f"{'·'.join(c['traits'][:2])}, "
             f"置身于{c['race']}风格的幻想场景中, "
             f"{c['art_style_desc']}, cinematic lighting, {c['qualifier']}, masterpiece"),

            # 特写肖像
            (f"close-up portrait, {gender_en}, {c['race']} {c['class']}, "
             f"{c['hair']} hair, {c['eyes']} eyes, "
             f"{c['personality_trait']}, detailed facial features, "
             f"{c['art_style_desc']}, shallow depth of field, "
             f"{c['qualifier']}, breathtaking expression"),
        ]
        return random.choice(templates)

    def _build_negative(self):
        return ("bad quality, worst quality, blurry, distorted, deformed, ugly, "
                "extra fingers, bad anatomy, cloned face, watermark, text, signature, "
                "generic AI face, doll-like eyes, featureless skin, perfect symmetry, "
                "uncanny valley, missing limbs, disfigured, oversaturated, "
                "lowres, jpeg artifacts, (worst quality:1.4), (bad anatomy:1.3)")

    def batch_create(self, count, specific_race=None, specific_class=None):
        """Create multiple unique characters."""
        characters = []
        for i in range(count):
            # Ensure uniqueness
            for _ in range(20):  # Try up to 20 times for a unique combo
                c = self.create_character(race=specific_race, cls=specific_class)
                combo = (c["race"], c["subtype"], c["class"], c["hair"], c["eyes"])
                if combo not in self._used_combos:
                    self._used_combos.add(combo)
                    characters.append(c)
                    break
            else:
                # Force a different combo
                c = self.create_character(
                    race=random.choice([r for r in RACES if r != (specific_race or "")]),
                    cls=random.choice([cl for cl in CLASSES if cl != (specific_class or "")])
                )
                characters.append(c)
        return characters


def main():
    parser = argparse.ArgumentParser(description="角色工厂 — 自动角色概念生成")
    parser.add_argument("--count", type=int, default=10, help="创建角色数量")
    parser.add_argument("--race", default=None, help="限定种族")
    parser.add_argument("--class", dest="cls_name", default=None, help="限定职业")
    parser.add_argument("--output", default="character_concepts.json", help="输出文件")
    parser.add_argument("--run", action="store_true", help="生成概念后立即启动 GPT 提示词优化")
    args = parser.parse_args()

    factory = CharacterFactory()
    characters = factory.batch_create(args.count, args.race, args.cls_name)

    output_path = Path("styleforge_pipeline") / "output" / args.output
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": datetime.now().isoformat(),
            "count": len(characters),
            "characters": characters,
        }, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*70}")
    print(f"  Character Factory — {len(characters)} unique characters created")
    print(f"{'='*70}\n")
    for i, c in enumerate(characters):
        print(f"  [{i+1:3d}] {c['name']:20s} | {c['race']}{c['subtype']}·{c['class']} | "
              f"{c['hair']}发·{c['eyes']}眸 | {c['personality']}")
    print(f"\n  Saved to: {output_path}")
    print(f"\n  下一步: python character_design.py --name \"{characters[0]['name']}\" ...")
    print(f"  批量运行: python character_batch.py --from {args.output}\n")


if __name__ == "__main__":
    main()
