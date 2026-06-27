# StyleForge Creative Studio

AI 图像与视频生成 | Ideogram 4 + FLUX.2 + Qwen Image + Wan 2.1 | RTX 4060 8GB 优化版

基于 ComfyUI v0.24.0 的一键式创意工作室，MJ/SD 风格的简洁 Web 界面，底层完全封装。

## 功能

| 模块 | 状态 | 说明 |
|------|------|------|
| 文生图 | 已验证 | Ideogram 4 (排版/文字) / FLUX.2 Klein (写实) / Qwen Image (中文) |
| 图生图 | 已验证 | Qwen Image 参考图编辑 |
| 换脸 | 已验证 | ReActor |
| 文生视频 | 实验 | Wan 2.1 T2V 1.3B，480p 81帧 |
| 图生视频 | 实验 | Wan I2V（start_image），480p |
| 角色生视频 | 实验 | Image → Wan I2V → ReActor 换脸 |
| 视频换脸 | 实验 | Wan I2V + ReActor 逐帧换脸 |

## 硬件要求

- **最低**: RTX 4060 8GB（--lowvram 模式，512×512 图像 / 480p 视频）
- **推荐**: RTX 4090 24GB（全功能，1024×1024 / 720p 视频）
- **磁盘**: ~60GB（模型文件）
- **系统**: Windows 10/11，Python 3.12+

## 快速开始

```powershell
# 1. 克隆 ComfyUI
git clone https://github.com/comfyanonymous/ComfyUI.git
cd ComfyUI

# 2. 下载 StyleForge 文件到 ComfyUI 根目录

# 3. 创建虚拟环境并安装依赖
python -m venv comfy_env
comfy_env\Scripts\pip install -r requirements.txt

# 4. 下载模型
comfy_env\Scripts\python download_models.py

# 5. 一键启动
start.bat
```

浏览器自动打开 `http://127.0.0.1:7860`

## 所需模型

| 模型 | 大小 | 用途 |
|------|------|------|
| Ideogram 4 NF4 | 12GB | **主力** 排版设计/文字渲染 (9.3B DiT) |
| FLUX.2 Klein 4B FP8 | 9GB | 写实摄影/自然场景 (4B DiT) |
| Qwen Image FP8 | 20GB | 中文原生/图生图编辑 |
| Qwen VL 7B FP8 | 8.8GB | Qwen Image 文本编码 |
| Qwen Image VAE | 243MB | Qwen Image 编解码 |
| Wan T2V 1.3B | 5.3GB | 文生视频 |
| Wan VAE | 485MB | 视频编解码 |
| umT5-XXL | 10.7GB | Wan 文本编码 |
| ReActor (inswapper) | ~500MB | 换脸 |

## 文件结构

```
ComfyUI/
├── styleforge_webui.py      # Gradio Web 界面 (多模型支持)
├── styleforge_config.yaml   # 模型配置 (本地/云端双环境)
├── start.bat                # 一键启动脚本
├── launch.ps1               # PowerShell 启动器（高级）
├── download_models.py       # 模型下载脚本
├── prompts/
│   └── prompt_library.json  # 50+ 条中英提示词库
├── workflows/
│   ├── image/               # 图像工作流
│   │   ├── 01-txt2img/      # 文生图
│   │   ├── 02-img2img/      # 图生图
│   │   └── 03-faceswap/     # 换脸
│   ├── video/               # 视频工作流
│   │   ├── 01-t2v/          # 文生视频
│   │   ├── 02-i2v/          # 图生视频
│   │   └── 03-faceswap-video/ # 视频换脸
│   └── full_pipeline/       # 全流程
│       └── char_to_video.json # 角色→视频
└── civitai_search.py        # CivitAI 提示词搜索
```

## 提示词指南

### Ideogram 4 (排版设计/文字渲染)
```
# 英文自然语言 — 支持 JSON 结构化提示词做精确布局控制
A minimalist poster with bold "STYLEFORGE" text centered, geometric shapes, navy blue and gold palette, clean design
```

### FLUX.2 Klein (写实摄影)
```
# 自然语言，英文效果最佳
A cinematic portrait of a woman in golden hour lighting, shallow depth of field, 85mm lens, photorealistic
```

### Qwen Image / Wan 2.1 (通义系列，原生中文)
```
# 中文（推荐 — 模型训练数据就是完整中文句子）
二次元动漫风格，一个少女站在樱花树下，长发飘飘，柔和的自然光，新海诚画风
```

与 SD/SDXL 不同，不需要 tag 堆砌，自然语言描述效果更好。

## 已知限制

- Ideogram 4 NF4 需 24GB 显存（当前本地用 FP8 版本替代方案：ideogram-4-fp8）
- Qwen Image FP8 20GB 在 8GB 显存上只能跑 512×512，推荐使用 GGUF Q4 量化版
- Wan T2V 1.3B 视频质量有限（阿里未发布 I2V 1.3B，用 T2V + start_image 实现等效 I2V）
- 视频输出为帧序列，需 ffmpeg 合成 mp4
