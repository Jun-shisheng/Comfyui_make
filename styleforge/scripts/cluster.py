"""
StyleForge cluster.py — CLIP embedding → UMAP → HDBSCAN style clustering.

Produces:
  - clustering/embeddings.npy       (N × 768)
  - clustering/cluster_review.html  (visual review of each cluster)
  - clustering/style_map.json       (image path → cluster name + trigger word)
"""

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

# -- CLIP
try:
    import open_clip
    HAS_OPENCLIP = True
except ImportError:
    HAS_OPENCLIP = False

# -- Dimensionality reduction & clustering
try:
    import umap
    HAS_UMAP = True
except ImportError:
    HAS_UMAP = False

try:
    import hdbscan
    HAS_HDBSCAN = True
except ImportError:
    HAS_HDBSCAN = False


def _build_html(clusters: dict[int, list[dict]], output_path: Path) -> None:
    """Generate an interactive review HTML with 3×3 grids per cluster."""

    sections = []
    for cid in sorted(clusters.keys()):
        members = clusters[cid]
        sample = members[:9]
        cards = []
        for m in sample:
            rel = m["path"]
            cards.append(
                f'<div class="card">'
                f'<img src="{rel}" loading="lazy" style="width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px;">'
                f'</div>'
            )
        grid = '<div class="grid">' + "".join(cards) + "</div>"
        sections.append(
            f'<div class="cluster-section">'
            f'<h3>Cluster {cid}  <span class="count">{len(members)} images</span></h3>'
            f'{grid}'
            f'</div>'
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>StyleForge — Cluster Review</title>
<style>
  body {{ font-family: system-ui, sans-serif; background: #0f0f0f; color: #e0e0e0; padding: 24px; }}
  h2 {{ margin-bottom: 4px; }}
  .subtitle {{ color: #888; font-size: 14px; margin-bottom: 32px; }}
  .cluster-section {{ margin-bottom: 48px; border: 1px solid #2a2a2a; border-radius: 12px; padding: 20px; }}
  .cluster-section h3 {{ margin: 0 0 16px 0; }}
  .count {{ font-weight: normal; color: #888; font-size: 14px; }}
  .grid {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; }}
</style>
</head>
<body>
<h2>StyleForge Cluster Review</h2>
<p class="subtitle">{len(clusters)} clusters found. Review each group and assign style names.</p>
{"".join(sections)}
</body>
</html>"""

    output_path.write_text(html, encoding="utf-8")
    print(f"  Review page: {output_path}")


def _relative_path(abs_path: Path, base: Path) -> str:
    try:
        return abs_path.relative_to(base).as_posix()
    except ValueError:
        return abs_path.as_posix()


def run(
    image_dir: Path,
    output_dir: Path,
    min_cluster_size: int = 8,
    umap_dims: int = 16,
    device: str = "cpu",
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    images = sorted(
        p for p in image_dir.rglob("*")
        if p.suffix.lower() in (".png", ".jpg", ".jpeg")
    )
    if not images:
        print("No images found in", image_dir)
        sys.exit(1)

    print(f"Found {len(images)} images.")

    # ---- Step 1: CLIP embeddings ----
    embeddings_path = output_dir / "embeddings.npy"
    if embeddings_path.exists():
        print("[1/4] Loading cached embeddings...")
        embeddings = np.load(embeddings_path)
    else:
        if not HAS_OPENCLIP:
            print("ERROR: open_clip_torch not installed. Run: pip install open_clip_torch")
            sys.exit(1)
        print("[1/4] Extracting CLIP ViT-L/14 embeddings...")
        model, _, preprocess = open_clip.create_model_and_transforms(
            "ViT-L-14", pretrained="datacomp_xl_s13b_b90k"
        )
        model = model.to(device)
        model.eval()
        tokenizer = open_clip.get_tokenizer("ViT-L-14")

        batch_size = 16
        all_embeddings = []
        for i in range(0, len(images), batch_size):
            batch_paths = images[i : i + batch_size]
            batch_imgs = []
            for p in batch_paths:
                try:
                    img = Image.open(p).convert("RGB")
                    batch_imgs.append(preprocess(img))
                except Exception:
                    batch_imgs.append(preprocess(Image.new("RGB", (224, 224), (128, 128, 128))))
            img_tensor = np.stack([np.array(im) for im in batch_imgs])  # (B, 3, 224, 224)

            import torch
            with torch.no_grad():
                img_t = torch.from_numpy(img_tensor).to(device)
                feats = model.encode_image(img_t)
                feats = feats / feats.norm(dim=-1, keepdim=True)
                all_embeddings.append(feats.cpu().numpy())

            if (i // batch_size) % 10 == 0:
                print(f"  ... {min(i + batch_size, len(images))} / {len(images)}")

        embeddings = np.concatenate(all_embeddings, axis=0).astype(np.float32)
        np.save(embeddings_path, embeddings)
        print(f"  Saved: {embeddings_path}  ({embeddings.shape})")

    # ---- Step 2: UMAP ----
    if not HAS_UMAP:
        print("ERROR: umap-learn not installed. Run: pip install umap-learn")
        sys.exit(1)
    print(f"[2/4] UMAP: {embeddings.shape[1]}d → {umap_dims}d...")
    reducer = umap.UMAP(
        n_components=umap_dims,
        metric="cosine",
        n_neighbors=min(15, len(images) - 1),
        min_dist=0.1,
        random_state=42,
    )
    reduced = reducer.fit_transform(embeddings)
    print(f"  Reduced: {reduced.shape}")

    # ---- Step 3: HDBSCAN ----
    if not HAS_HDBSCAN:
        print("ERROR: hdbscan not installed. Run: pip install hdbscan")
        sys.exit(1)
    print(f"[3/4] HDBSCAN clustering (min_cluster_size={min_cluster_size})...")
    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        metric="euclidean",
        cluster_selection_epsilon=0.1,
    )
    labels = clusterer.fit_predict(reduced)
    unique_labels = set(labels)
    n_clusters = len(unique_labels - {-1})
    n_noise = int(np.sum(labels == -1))
    print(f"  Clusters: {n_clusters}  |  Noise: {n_noise}")

    # Assign noise to nearest cluster
    if n_noise > 0:
        cluster_centers = {}
        for lid in unique_labels:
            if lid == -1:
                continue
            cluster_centers[lid] = reduced[labels == lid].mean(axis=0)

        for idx in np.where(labels == -1)[0]:
            best_label = min(
                cluster_centers.keys(),
                key=lambda c: np.linalg.norm(reduced[idx] - cluster_centers[c]),
            )
            labels[idx] = best_label
        print(f"  Noise reassigned to nearest clusters.")

    # ---- Step 4: Build outputs ----
    print("[4/4] Generating outputs...")
    base = image_dir.parent.parent  # project root

    clusters: dict[int, list[dict]] = {}
    style_map: dict[str, str] = {}
    for idx, (img_path, lid) in enumerate(zip(images, labels)):
        cid = int(lid)
        clusters.setdefault(cid, []).append({
            "path": _relative_path(img_path, base),
            "embedding_idx": idx,
        })
        style_map[_relative_path(img_path, base)] = {
            "cluster_id": cid,
            "style_name": f"style_{cid:02d}",
            "trigger_word": f"style_{cid:02d}",
        }

    # HTML review
    _build_html(clusters, output_dir / "cluster_review.html")

    # style_map.json
    map_path = output_dir / "style_map.json"
    map_path.write_text(json.dumps(style_map, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  Style map: {map_path}")

    # Summary
    print(f"\n{'='*50}")
    print(f"Clustering complete: {len(clusters)} groups")
    for cid in sorted(clusters.keys()):
        print(f"  style_{cid:02d}: {len(clusters[cid]):4d} images")
    print(f"\nNext: Review {output_dir / 'cluster_review.html'} in browser.")
    print(f"      Rename styles and set trigger words in style_map.json.")


def main():
    parser = argparse.ArgumentParser(description="StyleForge CLIP style clustering")
    parser.add_argument("--images", default="data/standardized", help="Standardized images directory")
    parser.add_argument("--out", default="clustering", help="Output directory for cluster artifacts")
    parser.add_argument("--min-cluster-size", type=int, default=8, help="HDBSCAN minimum cluster size")
    parser.add_argument("--device", default="cpu", help="Device for CLIP: 'cpu' or 'cuda'")
    parser.add_argument("--project-root", default=None, help="Project root")
    args = parser.parse_args()

    if args.project_root:
        root = Path(args.project_root)
    else:
        root = Path(__file__).resolve().parent.parent

    image_dir = root / args.images
    output_dir = root / args.out

    if not image_dir.exists():
        print(f"Image directory not found: {image_dir}")
        print("Run preprocess.py first.")
        sys.exit(1)

    run(image_dir, output_dir, min_cluster_size=args.min_cluster_size, device=args.device)


if __name__ == "__main__":
    main()
