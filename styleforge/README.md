# StyleForge

ComfyUI 多风格角色创作管线。从 Pixiv / Pinterest 图片中自动聚类识别画风，训练独立 LoRA，叠加角色一致性和姿势控制出图。

**硬件目标：笔记本 RTX 4060 8GB，零付费依赖。**

## 快速开始

```bash
# 1. 安装依赖
pip install Pillow imagehash open_clip_torch umap-learn hdbscan numpy

# 2. 放入数据
#    data/raw/pixiv/    ← .pxiv 文件
#    data/raw/pinterest/ ← Pinterest 图片

# 3. 预处理
python scripts/preprocess.py

# 4. 聚类
python scripts/cluster.py
# → 浏览器打开 clustering/cluster_review.html 审查结果
# → 编辑 clustering/style_map.json 命名风格和触发词

# 5. 训练一个风格
python scripts/train_one_style.py style_03 --rank 8 --steps 1500

# 6. 在 ComfyUI 中加载 loras/ 目录下的 .safetensors 使用
```

## 目录结构

```
styleforge/
├── data/
│   ├── raw/            # 原始数据
│   ├── standardized/   # 预处理后的统一 PNG
│   └── datasets/       # 按风格分组的训练集 (img + .txt)
├── loras/              # 训练产出的 LoRA 文件
├── clustering/         # embeddings + 聚类结果 + style_map.json
├── workflows/          # ComfyUI 工作流模板
│   └── community/      # 精选社区工作流
├── scripts/            # 核心脚本
├── output/             # 生成图片输出
└── config.yaml         # 全局配置
```

## 脚本说明

| 脚本 | 功能 |
|------|------|
| `preprocess.py` | 数据标准化：解包 .pxiv、格式转换、缩放、去重、过滤 |
| `cluster.py` | CLIP embedding → UMAP → HDBSCAN 自动聚类 |
| `train_one_style.py` | 单风格 LoRA 训练（包装 AI Toolkit） |

## 推理工作流

在 ComfyUI 中加载 `workflows/` 目录下的模板：

1. **single_style_char.json** — 固定角色 + 指定风格 + 指定姿势
2. **batch_poses.json** — 同角色/风格，批量切换姿势
3. **multi_style_compare.json** — 同角色/姿势，多风格对比

## 硬件限制与降级策略

| 场景 | 策略 |
|------|------|
| 训练 OOM | 降 Rank (16→8)、用 Klein 4B 替代 Flux.1 Dev |
| 推理 OOM | 逐级卸载 ControlNet → IP-Adapter → 纯 LoRA |
| CLIP 太慢 | 默认用 CPU（1000 张约 3 分钟），可用 --device cuda 加速 |
