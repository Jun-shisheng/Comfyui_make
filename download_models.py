"""Download models via direct HTTP with progress bar and retry."""
import os
import time
import requests
from tqdm import tqdm

HF_BASE = "https://hf-mirror.com"
MODELS_DIR = r"G:\ComfyUI\models"

MODELS = [
    {
        "url": f"{HF_BASE}/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors",
        "dest": os.path.join(MODELS_DIR, "checkpoints", "sd_xl_base_1.0.safetensors"),
        "name": "SDXL 1.0 base (~6.5GB)",
    },
    {
        "url": f"{HF_BASE}/madebyollin/sdxl-vae-fp16-fix/resolve/main/sdxl_vae.safetensors",
        "dest": os.path.join(MODELS_DIR, "vae", "sdxl_vae.safetensors"),
        "name": "SDXL fp16 VAE (~320MB)",
    },
    {
        "url": f"{HF_BASE}/black-forest-labs/FLUX.2-Klein-4B/resolve/main/flux-2-klein-4b.safetensors",
        "dest": os.path.join(MODELS_DIR, "diffusion_models", "flux-2-klein-4b", "flux-2-klein-4b.safetensors"),
        "name": "FLUX.2 Klein 4B (~8GB)",
    },
]

def download(url, dest, name, max_retries=5):
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    for attempt in range(max_retries):
        try:
            existing_size = os.path.getsize(dest) if os.path.exists(dest) else 0

            if existing_size > 100_000_000:
                print(f"  [{name}] resuming from {existing_size/1e9:.1f}GB (attempt {attempt+1}/{max_retries})")
            else:
                print(f"  [{name}] downloading... (attempt {attempt+1}/{max_retries})")

            headers = {}
            if existing_size > 0:
                headers["Range"] = f"bytes={existing_size}-"

            resp = requests.get(url, stream=True, headers=headers, timeout=60)
            mode = "ab" if existing_size > 0 else "wb"

            if resp.status_code not in (200, 206):
                print(f"  HTTP {resp.status_code}, retrying in 10s...")
                time.sleep(10)
                continue

            total = int(resp.headers.get("content-length", 0)) + existing_size

            with open(dest, mode) as f, tqdm(
                total=total, unit="B", unit_scale=True, unit_divisor=1024,
                desc=name.split("(")[0].strip(), initial=existing_size
            ) as bar:
                for chunk in resp.iter_content(chunk_size=8 * 1024 * 1024):
                    f.write(chunk)
                    bar.update(len(chunk))

            final_size = os.path.getsize(dest)
            if final_size > 100_000_000:
                print(f"  -> done ({final_size/1e9:.1f}GB)")
            return True

        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.ChunkedEncodingError) as e:
            print(f"  Network error: {type(e).__name__}")
            if attempt < max_retries - 1:
                wait = (attempt + 1) * 15
                print(f"  Retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  Failed after {max_retries} attempts")
                return False

    return False

if __name__ == "__main__":
    for i, m in enumerate(MODELS, 1):
        print(f"\n[{i}/{len(MODELS)}] {m['name']}")
        download(m["url"], m["dest"], m["name"])

    print("\nDone. Check above for any errors.")
