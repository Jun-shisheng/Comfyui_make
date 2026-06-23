"""Prompt Engine — generates varied, high-quality prompts for the pipeline."""
import random
import json
import os

# 角色设计核心词汇库
CHARACTER_BASES = {
    "anime": [
        "anime style, cel shaded, vibrant colors",
        "二次元动漫风格, 赛璐璐上色",
        "JRPG character design, fantasy armor details",
        "Genshin Impact style, elemental effects",
        "Studio Ghibli inspired, soft watercolor texture",
        "90s anime aesthetic, hand-drawn line art feel",
        "Honkai Star Rail style, futuristic fashion",
    ],
    "realistic": [
        "photorealistic, cinematic lighting, 8K",
        "电影级写实, 自然光, 皮肤质感细腻",
        "dark fantasy realism, Elden Ring inspired",
        "historical epic film character, detailed costume",
        "cyberpunk photorealism, neon lighting, Blade Runner aesthetic",
    ],
    "semi_real": [
        "semi-realistic, digital painting style",
        "半写实半动漫, 厚涂风格, 艺术感",
        "concept art style, character design sheet",
        "illustration style, detailed rendering, soft shading",
    ],
}

CHARACTER_TYPES = {
    "female": [
        "1girl, elegant features, expressive eyes",
        "女性角色, 独特的面部特征, 有辨识度的五官",
        "female warrior, battle-worn but beautiful",
        "young woman, intellectual look, glasses, subtle expression",
        "mature woman, dignified bearing, experienced eyes",
    ],
    "male": [
        "1boy, sharp jawline, determined expression",
        "男性角色, 棱角分明的面部, 深沉的目光",
        "male warrior, scarred but noble, muscular build",
        "young man, scholarly appearance, thoughtful gaze",
        "mature man, weathered face, commanding presence",
    ],
}

OUTFITS = [
    "fantasy armor with intricate engravings",
    "古风长袍, 丝绸刺绣, 飘逸下摆",
    "cyberpunk streetwear, LED accents, techwear",
    "Victorian steampunk attire, brass accessories, goggles",
    "现代高定时装, 前卫剪裁, 不对称设计",
    "futuristic military uniform, tactical gear",
    "wasteland survival gear, patched clothing, practical",
    "elegant evening dress, flowing fabric, jewel tones",
    "traditional Japanese kimono, modern reinterpretation",
    "monk robes, mystical symbols, weathered fabric",
]

SETTINGS = [
    "cherry blossom garden at golden hour",
    "樱花纷飞的古战场, 夕阳余晖",
    "neon-lit cyberpunk alley, rain-slicked streets",
    "ancient temple ruins, moss-covered stones, god rays",
    "floating sky islands, crystal formations, ethereal light",
    "dark forest, bioluminescent flora, mysterious atmosphere",
    "desert wasteland, sandstorm approaching, dramatic sky",
    "underwater palace, coral architecture, shimmering light",
    "space station interior, holographic displays, zero gravity",
    "Japanese onsen town, steam rising, lantern light",
]

COLOR_PALETTES = [
    "warms tones, gold and crimson",
    "cool blues and silver",
    "monochromatic with a single accent color",
    "pastel palette, soft and dreamy",
    "high contrast, dramatic chiaroscuro",
    "earth tones, natural and grounded",
    "neon against dark background",
]

POSE_VARIANTS = [
    "dynamic action pose, mid-combat",
    "contemplative seated pose",
    "standing confidently, arms crossed",
    "walking forward, wind in hair",
    "over-the-shoulder glance",
    "俯视45度角, 仰拍视角",
    "silhouette against bright background",
    "close-up portrait, shallow depth of field",
]

DISTINCTIVE_FEATURES = [
    "unique facial scar, adds character",
    "heterochromatic eyes, different colors",
    "intricate facial tattoo, cultural pattern",
    "unusual hair color gradient, natural-looking",
    "distinctive beauty mark placement",
    "asymmetrical hairstyle, avant-garde",
    "vitiligo patterns, celebrated uniqueness",
    "piercings and subtle body modifications",
]

ANTI_AI_FACE = [
    "natural facial asymmetry, realistic proportions",
    "visible skin texture, pores, subtle imperfections",
    "unique nose shape, not the generic AI nose",
    "expressive eyes with character, not doll-like",
    "realistic lip shape with subtle asymmetry",
    "自然的五官比例, 非对称美感",
    "有个性的面部特征, 拒绝千篇一律的网红脸",
]

# Scene prompts
SCENE_TYPES = [
    "epic fantasy landscape, floating mountains, crystal rivers",
    "cyberpunk megacity, layered streets, holographic advertisements",
    "ancient Chinese palace interior, intricate wood carvings, incense smoke",
    "post-apocalyptic city, nature reclaiming, hopeful atmosphere",
    "steampunk airship dock, gears and brass, sunset clouds",
    "Japanese shrine in autumn, red maple leaves, stone lanterns",
    "space colony interior, plants growing in zero-G, view of nebula",
    "underwater research facility, giant sea creatures outside windows",
    "desert oasis at twilight, ancient ruins, palm trees",
    "frozen tundra, aurora borealis, ice castle silhouette",
]


class PromptEngine:
    def __init__(self, config):
        self.cfg = config
        self._used_combos = set()
        self._char_count = 0
        self._variation_seed = 0

    def next_prompt(self, mode="characters"):
        if mode == "characters":
            return self._character_prompt()
        elif mode == "scenes":
            return self._scene_prompt()
        elif mode == "variants":
            return self._variant_prompt()
        return self._character_prompt()

    def negative_prompt(self, mode="characters"):
        base = "bad quality, worst quality, blurry, distorted, ugly, deformed, "
        if mode == "characters":
            base += "extra fingers, bad anatomy, cloned face, watermark, text, signature, "
            base += "generic AI face, doll-like eyes, featureless skin, perfect symmetry, uncanny valley, "
            base += "missing limbs, disfigured, oversaturated, jpeg artifacts"
        return base

    def _character_prompt(self):
        self._char_count += 1
        # Rotate through bases to get variety
        base_idx = self._char_count % len(CHARACTER_BASES)
        style_list = list(CHARACTER_BASES.values())
        base = random.choice(style_list[base_idx % len(style_list)])

        char_type = random.choice(CHARACTER_TYPES["female" if self._char_count % 3 != 0 else "male"])
        outfit = random.choice(OUTFITS)
        setting = random.choice(SETTINGS)
        color = random.choice(COLOR_PALETTES)
        pose = random.choice(POSE_VARIANTS)
        feature = random.choice(DISTINCTIVE_FEATURES)
        anti = random.choice(ANTI_AI_FACE)

        # Cycle through styles periodically
        cycle = self._char_count // 20
        templates = [
            # Template A: Full scene
            lambda: f"{base}, {char_type}, {outfit}, {setting}, {pose}, {color}, {feature}, {anti}, masterpiece",
            # Template B: Studio shot
            lambda: f"character design sheet, {char_type}, {outfit}, front view and back view, "
                    f"{base}, concept art, {feature}, {anti}, reference sheet, white background, high quality",
            # Template C: Mood portrait
            lambda: f"{char_type}, {pose}, {setting}, {color}, {base}, "
                    f"emotional expression, {feature}, {anti}, cinematic composition, masterpiece",
        ]

        prompt = templates[cycle % len(templates)]()

        # Avoid exact duplicates
        combo_key = hash(prompt)
        while combo_key in self._used_combos:
            prompt = templates[random.randint(0, len(templates)-1)]()
            combo_key = hash(prompt)
        self._used_combos.add(combo_key)
        if len(self._used_combos) > 10000:
            self._used_combos.clear()

        return prompt

    def _scene_prompt(self):
        scene = random.choice(SCENE_TYPES)
        color = random.choice(COLOR_PALETTES)
        templates = [
            f"{scene}, {color}, wide shot, epic scale, cinematic composition, masterpiece, 8K",
            f"concept art, {scene}, {color}, environmental design, mood painting, high detail",
            f"{scene}, dramatic lighting, {color}, atmospheric, breathtaking, award-winning composition",
        ]
        return random.choice(templates)

    def _variant_prompt(self):
        outfit = random.choice(OUTFITS)
        pose = random.choice(POSE_VARIANTS)
        setting = random.choice(SETTINGS)
        return (f"Same character, different outfit: {outfit}, {pose}, {setting}, "
                f"maintain exact facial identity, consistent character design, masterpiece")
