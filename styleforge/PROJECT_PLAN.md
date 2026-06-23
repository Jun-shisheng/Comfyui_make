# StyleForge — ComfyUI 多风格角色创作管线

## Context

构建一套基于 ComfyUI 的开放式多风格创作系统。核心目标：从 Pixiv 和 Pinterest 采集大量图片，通过 CLIP 自动聚类识别出 7-8+ 种明显不同的画风，每种风格训练独立 LoRA，然后在 ComfyUI 推理管线中叠加角色一致性（IP-Adapter）和姿势控制（ControlNet），实现对固定角色或原创角色、在任意已学风格下、多种姿势不重合的出图。

硬件：笔记本 RTX 4060 8GB 显存，不依赖任何付费服务。

---

## 整体架构

```
数据采集 → 标准化 → CLIP 聚类 → 分组 LoRA 训练 → ComfyUI 推理
  ↑ Pixiv       ↑ preprocess.py   ↑ cluster.py    ↑ AI Toolkit      ↑ 3个工作流JSON
  ↑ Pinterest                     ↑ UMAP+HDBSCAN   ↑ Klein 4B        ↑ LoRA + ControlNet + IP-Adapter
```

五大模块：
1. **数据采集与标准化** — Pixiv .pxiv 解包、Pinterest 散图导入、统一预处理
2. **CLIP 风格聚类** — CLIP ViT-L/14 embedding → UMAP 降维 → HDBSCAN 自动聚类 → 人工审查命名
3. **分组 LoRA 训练** — 每组独立 LoRA (Rank=8-16), FLUX.2 Klein 4B 底模, AI Toolkit
4. **ComfyUI 推理管线** — 三种工作流模板，三重控制叠加
5. **社区工作流整合** — 精选公开工作流入库，拿来即用或适配改造

---

## 模块详细设计

### 模块 1：数据采集与标准化

**Pixiv 源**：.pxiv 文件本质是 ZIP，Python zipfile 解包提取 JPEG/PNG，按画师 ID 分目录保留元数据。

**Pinterest 源**：gallery-dl 批量下载 Board 图片，或手动拖入 `raw/pinterest/`。

**预处理脚本 (preprocess.py)**：
1. 格式统一：全部转 PNG，丢弃 GIF/WEBM
2. 分辨率过滤：短边 < 512px 丢弃
3. 短边缩放至 1024px，长边等比缩放 (Lanczos)，保留原图比例
4. 感知哈希去重 (pHash, Hamming > 5 保留)
5. 内容过滤：去掉纯文字图、UI 截图（可选轻量分类器）
6. 输出：`data/standardized/img_NNNNN.png`

### 模块 2：CLIP 风格聚类

```
CLIP ViT-L/14 → embedding (N×768) → UMAP (768→16d) → HDBSCAN (自动发现簇)
```

- CLIP 模型：OpenCLIP ViT-L/14，纯 CPU 约 5 张/秒
- UMAP 降维到 16 维保留局部结构
- HDBSCAN min_cluster_size=8，不预设风格数量
- 噪声点分配到最近簇，不丢弃任何数据
- 产出 `cluster_review.html`（每簇 9 张代表图网格），人工确认+命名
- 最终产出 `style_map.json`（图片路径 → 风格名 + 触发词）

**CLIP 聚类已知局限**：偏向语义内容可能干扰风格判断（"都是蓝天背景"可能被聚在一起而非按画风）。通过人工审查 cluster_review.html 修正，且 HDBSCAN 参数可快速重调重跑。

### 模块 3：分组 LoRA 训练

**训练栈**：
- 底模：FLUX.2 Klein 4B GGUF Q4（唯一在 8GB 上可训练的风格底模）
- 训练器：AI Toolkit (ostris/ai-toolkit)，备用 Kohya_SS
- 精度：FP8 训练 + INT4 底模，显存峰值 ~7.5GB

**每组参数**：

| 参数 | 值 |
|------|-----|
| 图片数 | 10-30 张/组 |
| Rank | 8（简单风格）~16（复杂风格） |
| Alpha | Rank × 1 |
| 学习率 | 1e-4 |
| 总步数 | 图片数 × 80~120 |
| Batch Size | 1（不可调） |
| 分辨率 | 1024× bucket（保留原图比例） |
| 预计时长 | 每组 1-2 小时 |

**产出**：`loras/style_{name}.safetensors`（每个 15-30MB）+ `style_map.json` 元数据。

### 模块 4：ComfyUI 推理管线

**显存预算（推理）**：

| 组件 | 显存 |
|------|------|
| Klein 4B GGUF Q4 | ~3.2 GB |
| 风格 LoRA ×1 | ~0.03 GB |
| ControlNet OpenPose | ~1.5 GB |
| IP-Adapter | ~0.8 GB |
| VAE + 中间激活 | ~1.5 GB |
| **合计峰值** | **~7.0 GB ✓** |

**三种工作流模板**：
1. `single_style_char.json` — 固定角色(IP-Adapter) + 指定风格(LoRA) + 指定姿势(ControlNet)
2. `batch_poses.json` — 同一角色/风格，批量切换 OpenPose 骨架
3. `multi_style_compare.json` — 同角色/姿势，切换风格 LoRA 做对比

**OOM 降级方案**（四级）：
1. ControlNet 换小模型（1.5B→0.5B）
2. 去掉 IP-Adapter，纯 Prompt 描述角色
3. 去掉 ControlNet，纯 Prompt 控制姿势
4. 仅 LoRA + Prompt，只保证风格

### 模块 5：社区工作流整合

收录到 `workflows/community/`，含原始来源链接。

**直接适配**（与我们的架构重合）：
- Triple-Lock 角色一致性（IP-Adapter + LoRA + ControlNet 三层叠加）
- Character Sheet → LoRA（同角色多角度训练模板）
- Qwen Swap Anything + SAM3.1（精准遮罩换头/换装）

**拿来即用**：
- APEX FLOW（高分辨率修复 + 面部精修 + ControlNet + Inpainting）
- Smooth Workflow v4（轻量基础模板，适合入门）
- Lonecat Simple（多底模简化工作流 + Florence 辅助打标）

**进阶整合（后续可选）**：
- Combined Workflow v8.1（600+ 节点，Ollama/LLM prompt 扩展，可利用现有 Qwen 7B）
- Multi-Model Refiner（双 checkpoint 交叉精修，构图用 A、纹理用 B）

---

## 项目结构

```
styleforge/
├── data/
│   ├── raw/              # 原始数据：pixiv/ + pinterest/ 子目录
│   ├── standardized/      # 预处理后的统一 PNG
│   └── datasets/          # 按风格分组的训练集
│       ├── style_01/      # img + .txt 标注
│       ├── style_02/
│       └── ...
├── loras/                 # 训练产出的 LoRA 文件
│   ├── style_flat_cel.safetensors
│   ├── style_oily_thick.safetensors
│   └── ...
├── clustering/
│   ├── embeddings.npy     # N×768 CLIP 嵌入矩阵
│   ├── cluster_review.html # 聚类结果审查页
│   └── style_map.json     # 图片→风格 映射
├── workflows/
│   ├── community/         # 精选公开工作流 + 来源链接
│   ├── single_style_char.json
│   ├── batch_poses.json
│   └── multi_style_compare.json
├── scripts/
│   ├── preprocess.py      # 数据标准化
│   ├── cluster.py         # CLIP嵌入+UMAP+HDBSCAN
│   └── train_one_style.py # 单风格LoRA训练入口
├── output/                # 生成图片输出
├── config.yaml            # 全局配置
└── README.md
```

loras/ 通过 symlink 或直接路径指向 ComfyUI/models/loras/。

---

## 技术依赖

| 依赖 | 用途 | 安装方式 |
|------|------|----------|
| ComfyUI + Manager | 推理引擎 | 已有 (Sketch Agent) |
| FLUX.2 Klein 4B | 训练+推理底模 | HuggingFace 下载 (~8GB) |
| AI Toolkit | LoRA 训练 | git clone + pip |
| open_clip_torch | CLIP embedding | pip install |
| umap-learn + hdbscan | 聚类 | pip install |
| ControlNet + IP-Adapter 节点 | 姿势/角色控制 | ComfyUI Manager |

---

## 实施路线

### Phase 1 — 基础设施（1-2 天）
- 创建项目目录结构
- 实现 preprocess.py（Pixiv .pxiv 解包 + Pinterest 导入 + 6 步标准化）
- 收集首批数据（≥100 张）
- 实现 cluster.py（CLIP embedding + UMAP + HDBSCAN）
- 生成 cluster_review.html 验证聚类质量
- **交付物**：style_map.json + 分组数据集

### Phase 2 — 训练验证（2-3 天）
- 安装 AI Toolkit + Klein 4B
- 挑 2 个风格组做训练验证
- 调参：Rank / LR / 步数 / 触发词权重
- 在 ComfyUI 中验证 LoRA 可用性
- 确认显存预算（峰值不超过 7.8GB）
- 批量训练剩余风格组
- **交付物**：全部 LoRA 文件 + 训练日志

### Phase 3 — 推理管线（1-2 天）
- 基于 Triple-Lock 模板搭建 3 个自定义工作流
- 下载精选社区工作流到 workflows/community/
- 测试 IP-Adapter 角色一致性
- 测试 ControlNet 多姿势切换
- 调 LoRA 权重曲线
- **交付物**：工作流 JSON + 参数备忘

### Phase 4 — 扩展迭代（持续）
- 新增数据 → 增量聚类 → 补充 LoRA
- 淘汰不满意的风格 → 重新聚类/训练
- 扩展姿势库（预设常用骨架）
- 可选：Gradio WebUI 简化操作

---

## 验证方法

1. **聚类验证**：cluster_review.html 中每簇图片在视觉上属于同一风格，无明显杂糅
2. **训练验证**：LoRA 权重 0.4-0.5 时风格明显但姿势/角色仍可 Prompt 自由控制（不过拟合）
3. **推理验证**：同一角色 + 3 种不同 OpenPose 骨架 → 出图风格一致、姿势不重合、角色长相一致
4. **显存验证**：训练和推理全程显存不超过 7.8GB，无 CUDA OOM
5. **风格覆盖验证**：至少 7 种风格可独立触发，风格间切换后出图有明显视觉差异
