"""
StyleForge preprocess.py — Data ingestion and standardization.

Handles:
  - Pixiv .pxiv files (ZIP archives containing JPEG/PNG)
  - Pinterest loose images (manual drag-in or gallery-dl output)
  - GIF/WEBM → discard
  - Short side < 512px → discard
  - Short side → 1024px, long side proportional (Lanczos)
  - Perceptual hash dedup (pHash, Hamming distance)
  - Output: data/standardized/img_NNNNN.png
"""

import argparse
import io
import json
import os
import shutil
import sys
import zipfile
from pathlib import Path

from PIL import Image, UnidentifiedImageError

# Optional: imagehash for dedup
try:
    import imagehash
    HAS_IMAGEHASH = True
except ImportError:
    HAS_IMAGEHASH = False


def extract_pixiv(pixiv_dir: Path, output_dir: Path) -> int:
    """Extract .pxiv (ZIP) files. Preserve artist_id subdirectories."""
    count = 0
    for pxiv_file in pixiv_dir.rglob("*.pxiv"):
        try:
            with zipfile.ZipFile(pxiv_file, "r") as zf:
                artist = pxiv_file.stem
                dest = output_dir / artist
                dest.mkdir(parents=True, exist_ok=True)
                for member in zf.namelist():
                    ext = member.rsplit(".", 1)[-1].lower() if "." in member else ""
                    if ext in ("jpg", "jpeg", "png", "webp"):
                        data = zf.read(member)
                        img = Image.open(io.BytesIO(data))
                        out_name = f"{artist}_{count:05d}.png"
                        img.save(dest / out_name, "PNG")
                        count += 1
            print(f"  [pixiv] {pxiv_file.name} → {count} images")
        except (zipfile.BadZipFile, OSError) as e:
            print(f"  [warn] bad pixiv file {pxiv_file}: {e}")
    return count


def import_pinterest(pinterest_dir: Path, output_dir: Path) -> int:
    """Copy PNG/JPEG/WEBP from pinterest directory into standardized staging."""
    count = 0
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    for img_path in pinterest_dir.rglob("*"):
        if img_path.suffix.lower() in valid_exts:
            dest = output_dir / f"pin_{count:05d}{img_path.suffix.lower()}"
            shutil.copy2(img_path, dest)
            count += 1
    print(f"  [pinterest] {count} images imported")
    return count


def standardize(
    input_dir: Path,
    output_dir: Path,
    short_side_target: int = 1024,
    min_short_side: int = 512,
    dedup_threshold: int = 5,
) -> int:
    """
    Process all images in input_dir:
      1. Convert to PNG
      2. Discard if short side < min_short_side
      3. Scale short side to short_side_target (Lanczos)
      4. pHash dedup
    """
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}
    images: list[Path] = []
    for img_path in sorted(input_dir.rglob("*")):
        if img_path.suffix.lower() in valid_exts:
            images.append(img_path)

    if not images:
        print("  No images found.")
        return 0

    hashes: list[imagehash.ImageHash] = []
    kept = 0

    for i, img_path in enumerate(images):
        try:
            img = Image.open(img_path).convert("RGB")
        except (UnidentifiedImageError, OSError):
            print(f"  [skip] unreadable: {img_path.name}")
            continue

        w, h = img.size
        short, long = (w, h) if w < h else (h, w)

        if short < min_short_side:
            print(f"  [skip] too small ({short}px): {img_path.name}")
            continue

        # Scale
        ratio = short_side_target / short
        new_short = short_side_target
        new_long = int(long * ratio)
        new_size = (new_long, new_short) if w > h else (new_short, new_long)

        img = img.resize(new_size, Image.LANCZOS)

        # Dedup
        if HAS_IMAGEHASH:
            h = imagehash.phash(img)
            dup = any((h - eh) < dedup_threshold for eh in hashes[-500:])
            if dup:
                print(f"  [dup] {img_path.name}")
                continue
            hashes.append(h)

        out_path = output_dir / f"img_{kept:06d}.png"
        img.save(out_path, "PNG")
        kept += 1

        if kept % 50 == 0:
            print(f"  ... {kept} / {i + 1} processed")

    print(f"  Standardized: {kept} images kept (from {len(images)} candidates)")
    return kept


def run(raw_dir: Path, standardized_dir: Path) -> None:
    standardized_dir.mkdir(parents=True, exist_ok=True)

    pixiv_in = raw_dir / "pixiv"
    pinterest_in = raw_dir / "pinterest"

    # Stage all source images into a temp staging area, then standardize
    staging = standardized_dir.parent / "_staging"
    staging.mkdir(parents=True, exist_ok=True)

    total = 0
    if pixiv_in.exists() and any(pixiv_in.iterdir()):
        print("[1/3] Extracting Pixiv .pxiv files...")
        total += extract_pixiv(pixiv_in, staging)

    if pinterest_in.exists() and any(pinterest_in.iterdir()):
        print("[2/3] Importing Pinterest images...")
        total += import_pinterest(pinterest_in, staging)

    print(f"[3/3] Standardizing ({total} raw images)...")
    kept = standardize(staging, standardized_dir)

    # Cleanup staging
    shutil.rmtree(staging, ignore_errors=True)

    print(f"\nDone. {kept} images in {standardized_dir}")
    with open(standardized_dir / "manifest.json", "w") as f:
        json.dump({"count": kept, "source_pixiv": str(pixiv_in), "source_pinterest": str(pinterest_in)}, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="StyleForge data preprocessor")
    parser.add_argument("--raw", default="data/raw", help="Raw data directory")
    parser.add_argument("--out", default="data/standardized", help="Output directory")
    parser.add_argument("--project-root", default=None, help="Project root (defaults to parent of script)")
    args = parser.parse_args()

    if args.project_root:
        root = Path(args.project_root)
    else:
        root = Path(__file__).resolve().parent.parent

    raw_dir = root / args.raw
    standardized_dir = root / args.out

    if not raw_dir.exists():
        print(f"Raw data directory not found: {raw_dir}")
        print("Expected structure:")
        print(f"  {raw_dir}/pixiv/  ← drop .pxiv files here")
        print(f"  {raw_dir}/pinterest/  ← drop Pinterest images here")
        sys.exit(1)

    run(raw_dir, standardized_dir)


if __name__ == "__main__":
    main()
