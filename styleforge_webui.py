"""
StyleForge WebUI - Simple MJ/SD-like interface for ComfyUI
Launches a clean Gradio web interface that calls ComfyUI API in background.
"""
import json
import os
import sys
import uuid
import time
import urllib.request
import urllib.parse
import urllib.error
import base64
import io
import yaml
from pathlib import Path

COMFYUI_URL = "http://127.0.0.1:8188"
PROMPT_LIBRARY_PATH = os.path.join(os.path.dirname(__file__), "prompts", "prompt_library.json")
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "styleforge_config.yaml")

# Import Gradio
try:
    import gradio as gr
except ImportError:
    print("Installing gradio...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "gradio"])
    import gradio as gr


def load_config():
    """Load StyleForge configuration, auto-detecting environment."""
    if not os.path.exists(CONFIG_PATH):
        return {"environment": "local"}
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    # Auto-detect: if VRAM >= 20GB, switch to cloud profile
    env = cfg.get("environment", "local")
    if env == "auto":
        try:
            import subprocess, re
            out = subprocess.check_output(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], text=True)
            vram_mb = int(re.findall(r'\d+', out)[0])
            env = "cloud_4090" if vram_mb >= 20000 else "local"
        except:
            env = "local"
    return cfg, env


def queue_prompt(prompt_workflow):
    """Submit workflow to ComfyUI and get prompt_id."""
    data = json.dumps({"prompt": prompt_workflow}).encode("utf-8")
    req = urllib.request.Request(f"{COMFYUI_URL}/prompt", data=data)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except Exception as e:
        raise Exception(f"Cannot connect to ComfyUI at {COMFYUI_URL}. Make sure ComfyUI is running.")


def get_history(prompt_id):
    """Get execution history for a prompt."""
    try:
        with urllib.request.urlopen(f"{COMFYUI_URL}/history/{prompt_id}") as resp:
            return json.loads(resp.read())
    except:
        return None


def get_image(filename, subfolder="", folder_type="output"):
    """Download image from ComfyUI output."""
    data = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    url_values = urllib.parse.urlencode(data)
    try:
        with urllib.request.urlopen(f"{COMFYUI_URL}/view?{url_values}") as resp:
            return resp.read()
    except:
        return None


def load_prompt_library():
    """Load built-in prompt library."""
    if os.path.exists(PROMPT_LIBRARY_PATH):
        with open(PROMPT_LIBRARY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"categories": {}}


def load_workflow(template_name):
    """Load a workflow JSON template."""
    workflows_dir = os.path.join(os.path.dirname(__file__), "workflows")
    for root, dirs, files in os.walk(workflows_dir):
        for f in files:
            if f == f"{template_name}.json":
                path = os.path.join(root, f)
                with open(path, "r", encoding="utf-8") as fh:
                    return json.load(fh)
    return None


def get_available_workflows():
    """List all available workflow templates."""
    workflows = []
    workflows_dir = os.path.join(os.path.dirname(__file__), "workflows")
    if os.path.exists(workflows_dir):
        for root, dirs, files in os.walk(workflows_dir):
            for f in files:
                if f.endswith(".json"):
                    name = os.path.splitext(f)[0]
                    rel = os.path.relpath(os.path.join(root, f), workflows_dir)
                    workflows.append((name, rel))
    return workflows


def _get_model(cfg, env, section, key, default=None):
    """Resolve a model path from config for current environment."""
    try:
        return cfg[section][env][key]
    except (KeyError, TypeError):
        return default


def build_txt2img_workflow(prompt, negative_prompt, width, height, seed, model="qwen_image"):
    cfg, env = load_config()

    if model == "ideogram4":
        return build_ideogram4_workflow(cfg, env, prompt, negative_prompt, width, height, seed)
    elif model == "flux2":
        return build_flux2_workflow(cfg, env, prompt, negative_prompt, width, height, seed)
    else:
        return build_qwen_image_workflow(cfg, env, prompt, negative_prompt, width, height, seed)


def build_qwen_image_workflow(cfg, env, prompt, negative_prompt, width, height, seed):
    m = cfg.get("image", {}).get("txt2img", {}).get(env, {})
    steps = m.get("steps", 12 if env == "local" else 20)
    cfg_val = m.get("cfg", 3.5)
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": m["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["clip"], "type": m["clip_type"]}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
        "4": {"class_type": "TextEncodeQwenImageEdit", "inputs": {"clip": ["2", 0], "prompt": prompt}},
        "5": {"class_type": "TextEncodeQwenImageEdit", "inputs": {"clip": ["2", 0], "prompt": negative_prompt}},
        "6": {"class_type": "EmptyQwenImageLayeredLatentImage", "inputs": {"width": width, "height": height, "layers": 3, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "seed": seed, "steps": steps, "cfg": cfg_val, "sampler_name": "dpmpp_2m", "scheduler": "normal", "denoise": 1.0}},
        "8": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["7", 0], "vae": ["3", 0], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
        "9": {"class_type": "PreviewImage", "inputs": {"images": ["8", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "qwen_txt2img"}},
    }


def build_ideogram4_workflow(cfg, env, prompt, negative_prompt, width, height, seed):
    m = cfg.get("image", {}).get("ideogram4", {}).get(env, {})
    if not m:
        return None
    steps = m.get("steps", 10)
    cfg_val = m.get("cfg", 0.0)
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": m["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["clip"], "type": m["clip_type"]}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["2", 0]}},
        "6": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "Ideogram4Scheduler", "inputs": {"steps": steps, "width": width, "height": height, "mu": 0.0, "std": 1.75}},
        "8": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "9": {"class_type": "SamplerCustom", "inputs": {"model": ["1", 0], "add_noise": True, "noise_seed": seed, "cfg": cfg_val, "positive": ["4", 0], "negative": ["5", 0], "sampler": ["8", 0], "sigmas": ["7", 0], "latent_image": ["6", 0]}},
        "10": {"class_type": "VAEDecode", "inputs": {"samples": ["9", 0], "vae": ["3", 0]}},
        "11": {"class_type": "PreviewImage", "inputs": {"images": ["10", 0]}},
        "12": {"class_type": "SaveImage", "inputs": {"images": ["10", 0], "filename_prefix": "ideogram4_txt2img"}},
    }


def build_flux2_workflow(cfg, env, prompt, negative_prompt, width, height, seed):
    m = cfg.get("image", {}).get("flux2", {}).get(env, {})
    if not m:
        return None
    steps = m.get("steps", 25)
    cfg_val = m.get("cfg", 2.0)
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": m["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["clip"], "type": m["clip_type"]}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["t5"], "type": m["clip_type"]}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["3", 0]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["2", 0]}},
        "8": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["3", 0]}},
        "9": {"class_type": "EmptyFlux2LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "10": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "euler"}},
        "11": {"class_type": "BasicScheduler", "inputs": {"model": ["1", 0], "scheduler": "simple", "steps": steps, "denoise": 1.0}},
        "12": {"class_type": "SamplerCustom", "inputs": {"model": ["1", 0], "add_noise": True, "noise_seed": seed, "cfg": cfg_val, "positive": ["5", 0], "negative": ["7", 0], "sampler": ["10", 0], "sigmas": ["11", 0], "latent_image": ["9", 0]}},
        "13": {"class_type": "VAEDecode", "inputs": {"samples": ["12", 0], "vae": ["4", 0]}},
        "14": {"class_type": "PreviewImage", "inputs": {"images": ["13", 0]}},
        "15": {"class_type": "SaveImage", "inputs": {"images": ["13", 0], "filename_prefix": "flux2_txt2img"}},
    }


def build_img2img_workflow(prompt, negative_prompt, ref_image_b64, width, height, seed):
    cfg, env = load_config()
    m = cfg.get("image", {}).get("txt2img", {}).get(env, {})
    input_dir = os.path.join(os.path.dirname(__file__), "input")
    os.makedirs(input_dir, exist_ok=True)
    ref_path = os.path.join(input_dir, "ref_img2img.png")
    if ref_image_b64:
        raw = ref_image_b64.split(",")[-1] if "," in ref_image_b64 else ref_image_b64
        with open(ref_path, "wb") as f:
            f.write(base64.b64decode(raw))
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": m["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["clip"], "type": m["clip_type"]}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": "ref_img2img.png"}},
        "5": {"class_type": "TextEncodeQwenImageEdit", "inputs": {"clip": ["2", 0], "prompt": prompt, "vae": ["3", 0], "image": ["4", 0]}},
        "6": {"class_type": "TextEncodeQwenImageEdit", "inputs": {"clip": ["2", 0], "prompt": negative_prompt}},
        "7": {"class_type": "EmptyQwenImageLayeredLatentImage", "inputs": {"width": width, "height": height, "layers": 3, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["5", 0], "negative": ["6", 0], "latent_image": ["7", 0], "seed": seed, "steps": m.get("steps", 12), "cfg": 2.5, "sampler_name": "dpmpp_2m", "scheduler": "normal", "denoise": 1.0}},
        "9": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["8", 0], "vae": ["3", 0], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
        "10": {"class_type": "PreviewImage", "inputs": {"images": ["9", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "qwen_img2img"}},
    }


def build_t2v_workflow(prompt, negative_prompt, duration, resolution, seed):
    cfg, env = load_config()
    m = cfg.get("video", {}).get("t2v", {}).get(env, {})
    if not m:
        return None
    if "720" in resolution:
        w, h = 1280, 720
    else:
        w, h = 832, 480
    length = ((duration * 16) // 4) * 4 + 1
    steps = m.get("steps", 20)
    cfg_val = m.get("cfg", 4.0)
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": m["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["clip"], "type": m["clip_type"]}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["2", 0]}},
        "6": {"class_type": "WanImageToVideo", "inputs": {"positive": ["4", 0], "negative": ["5", 0], "vae": ["3", 0], "width": w, "height": h, "length": length, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["6", 0], "negative": ["6", 1], "latent_image": ["6", 2], "seed": seed, "steps": steps, "cfg": cfg_val, "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["3", 0]}},
        "9": {"class_type": "PreviewImage", "inputs": {"images": ["8", 0]}},
        "10": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "wan_t2v"}},
    }


def build_i2v_workflow(prompt, negative_prompt, start_image_b64, duration, seed):
    cfg, env = load_config()
    m = cfg.get("video", {}).get("i2v", {}).get(env, {})
    if not m:
        return None
    input_dir = os.path.join(os.path.dirname(__file__), "input")
    os.makedirs(input_dir, exist_ok=True)
    ref_path = os.path.join(input_dir, "start_frame_i2v.png")
    if start_image_b64:
        raw = start_image_b64.split(",")[-1] if "," in start_image_b64 else start_image_b64
        with open(ref_path, "wb") as f:
            f.write(base64.b64decode(raw))
    length = ((duration * 16) // 4) * 4 + 1
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": m["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": m["clip"], "type": m["clip_type"]}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": m["vae"]}},
        "4": {"class_type": "LoadImage", "inputs": {"image": "start_frame_i2v.png"}},
        "5": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["2", 0]}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": negative_prompt, "clip": ["2", 0]}},
        "7": {"class_type": "WanImageToVideo", "inputs": {"positive": ["5", 0], "negative": ["6", 0], "vae": ["3", 0], "start_image": ["4", 0], "width": 832, "height": 480, "length": length, "batch_size": 1}},
        "8": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["7", 0], "negative": ["7", 1], "latent_image": ["7", 2], "seed": seed, "steps": m.get("steps", 20), "cfg": m.get("cfg", 4.0), "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["8", 0], "vae": ["3", 0]}},
        "10": {"class_type": "PreviewImage", "inputs": {"images": ["9", 0]}},
        "11": {"class_type": "SaveImage", "inputs": {"images": ["9", 0], "filename_prefix": "wan_i2v"}},
    }


def build_char_to_video_workflow(char_prompt, char_neg, motion_prompt, motion_neg, width, height, seed):
    cfg, env = load_config()
    img_m = cfg.get("image", {}).get("txt2img", {}).get(env, {})
    vid_m = cfg.get("video", {}).get("i2v", {}).get(env, {})
    if not vid_m:
        return None
    return {
        # === Stage 1: Qwen Image ===
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": img_m["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "CLIPLoader", "inputs": {"clip_name": img_m["clip"], "type": img_m["clip_type"]}},
        "3": {"class_type": "VAELoader", "inputs": {"vae_name": img_m["vae"]}},
        "4": {"class_type": "TextEncodeQwenImageEdit", "inputs": {"clip": ["2", 0], "prompt": char_prompt}},
        "5": {"class_type": "TextEncodeQwenImageEdit", "inputs": {"clip": ["2", 0], "prompt": char_neg}},
        "6": {"class_type": "EmptyQwenImageLayeredLatentImage", "inputs": {"width": width, "height": height, "layers": 3, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["1", 0], "positive": ["4", 0], "negative": ["5", 0], "latent_image": ["6", 0], "seed": seed, "steps": img_m.get("steps", 20), "cfg": img_m.get("cfg", 3.5), "sampler_name": "dpmpp_2m", "scheduler": "normal", "denoise": 1.0}},
        "8": {"class_type": "VAEDecodeTiled", "inputs": {"samples": ["7", 0], "vae": ["3", 0], "tile_size": 512, "overlap": 64, "temporal_size": 64, "temporal_overlap": 8}},
        # === Stage 2: Wan I2V ===
        "9": {"class_type": "UNETLoader", "inputs": {"unet_name": vid_m["unet"], "weight_dtype": "default"}},
        "10": {"class_type": "CLIPLoader", "inputs": {"clip_name": vid_m["clip"], "type": vid_m["clip_type"]}},
        "11": {"class_type": "VAELoader", "inputs": {"vae_name": vid_m["vae"]}},
        "12": {"class_type": "CLIPTextEncode", "inputs": {"text": motion_prompt, "clip": ["10", 0]}},
        "13": {"class_type": "CLIPTextEncode", "inputs": {"text": motion_neg, "clip": ["10", 0]}},
        "14": {"class_type": "WanImageToVideo", "inputs": {"positive": ["12", 0], "negative": ["13", 0], "vae": ["11", 0], "start_image": ["8", 0], "width": width, "height": height, "length": 81, "batch_size": 1}},
        "15": {"class_type": "KSampler", "inputs": {"model": ["9", 0], "positive": ["14", 0], "negative": ["14", 1], "latent_image": ["14", 2], "seed": seed + 1, "steps": vid_m.get("steps", 20), "cfg": vid_m.get("cfg", 4.0), "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "16": {"class_type": "VAEDecode", "inputs": {"samples": ["15", 0], "vae": ["11", 0]}},
        "17": {"class_type": "PreviewImage", "inputs": {"images": ["8", 0]}},
        "18": {"class_type": "PreviewImage", "inputs": {"images": ["16", 0]}},
        "19": {"class_type": "SaveImage", "inputs": {"images": ["16", 0], "filename_prefix": "char_to_video"}},
    }


def get_all_output_images(history_entry):
    """Extract all output image filenames from a history entry."""
    all_images = []
    outputs = history_entry.get("outputs", {})
    for node_id, node_output in outputs.items():
        images = node_output.get("images", [])
        for img in images:
            all_images.append(img)
    return all_images


def frames_to_video(frame_images, output_path, fps=16):
    """Combine downloaded PNG frames into an MP4 video using ffmpeg."""
    import tempfile
    import subprocess

    tmpdir = tempfile.mkdtemp(prefix="styleforge_frames_")
    frame_paths = []
    for i, img_bytes in enumerate(frame_images):
        fpath = os.path.join(tmpdir, f"frame_{i:05d}.png")
        with open(fpath, "wb") as f:
            f.write(img_bytes)
        frame_paths.append(fpath)

    if not frame_paths:
        return None

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-framerate", str(fps),
        "-i", os.path.join(tmpdir, "frame_%05d.png"),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "23",
        output_path
    ]
    subprocess.run(cmd, capture_output=True, check=True)

    for p in frame_paths:
        os.unlink(p)
    os.rmdir(tmpdir)
    return output_path


def poll_until_done(prompt_id, max_wait=1200):
    """Poll ComfyUI until execution completes. Returns history entry or None."""
    elapsed = 0
    while elapsed < max_wait:
        history = get_history(prompt_id)
        if history and prompt_id in history:
            return history[prompt_id]
        time.sleep(2)
        elapsed += 2
    return None


# ============ UI Generation Functions ============

def generate_txt2img(prompt, negative_prompt, width, height, seed, model):
    if seed == -1:
        seed = int(time.time() * 1000) % 2147483647

    wf = build_txt2img_workflow(prompt, negative_prompt, width, height, seed, model)

    try:
        result = queue_prompt(wf)
        prompt_id = result["prompt_id"]
        entry = poll_until_done(prompt_id, max_wait=1200)
        if entry is None:
            return None, "Timeout (10 min). Qwen Image FP8 is slow on 8GB VRAM."

        all_imgs = get_all_output_images(entry)
        if not all_imgs:
            # Check if prompt failed with errors
            status = entry.get("status", {})
            if status.get("completed") is False:
                return None, "Generation failed. Check ComfyUI terminal for CUDA errors."
            return None, "No output image generated."

        img_data = get_image(all_imgs[0]["filename"], all_imgs[0].get("subfolder", ""), all_imgs[0].get("type", "output"))
        if img_data:
            return img_data, f"Done! Seed: {seed}"
        return None, "Failed to download output image."
    except Exception as e:
        return None, str(e)


def generate_img2img(prompt, negative_prompt, ref_image, width, height, seed):
    if seed == -1:
        seed = int(time.time() * 1000) % 2147483647

    # Convert PIL image to base64
    img_b64 = None
    if ref_image is not None:
        buf = io.BytesIO()
        ref_image.save(buf, format="PNG")
        img_b64 = base64.b64encode(buf.getvalue()).decode()

    wf = build_img2img_workflow(prompt, negative_prompt, img_b64, width, height, seed)
    if wf is None:
        return None, "Workflow template not found!"

    try:
        result = queue_prompt(wf)
        prompt_id = result["prompt_id"]
        entry = poll_until_done(prompt_id, max_wait=1200)
        if entry is None:
            return None, "Timeout (10 min)."
        all_imgs = get_all_output_images(entry)
        if not all_imgs:
            return None, "No output image. Check ComfyUI terminal."
        img_data = get_image(all_imgs[0]["filename"], all_imgs[0].get("subfolder", ""), all_imgs[0].get("type", "output"))
        if img_data:
            return img_data, f"Done! Seed: {seed}"
        return None, "Failed to download output."
    except Exception as e:
        return None, str(e)


def generate_t2v(prompt, negative_prompt, duration, resolution, seed):
    if seed == -1:
        seed = int(time.time() * 1000) % 2147483647

    wf = build_t2v_workflow(prompt, negative_prompt, duration, resolution, seed)
    if wf is None:
        return None, "Workflow template 'wan_t2v' not found!"

    try:
        result = queue_prompt(wf)
        prompt_id = result["prompt_id"]
        entry = poll_until_done(prompt_id, max_wait=900)
        if entry is None:
            return None, "Timeout (15 min). Video generation is slow on 8GB VRAM."
        all_imgs = get_all_output_images(entry)
        if not all_imgs:
            return None, "No output frames. Check ComfyUI terminal for errors."

        frame_bytes_list = []
        for img_info in all_imgs:
            data = get_image(img_info["filename"], img_info.get("subfolder", ""), img_info.get("type", "output"))
            if data:
                frame_bytes_list.append(data)

        if not frame_bytes_list:
            return None, "Failed to download output frames."

        output_video = os.path.join(os.path.dirname(__file__), "output", f"t2v_{prompt_id}.mp4")
        os.makedirs(os.path.dirname(output_video), exist_ok=True)
        frames_to_video(frame_bytes_list, output_video, fps=16)
        return output_video, f"Done! {len(frame_bytes_list)} frames, seed: {seed}"
    except Exception as e:
        return None, str(e)


def generate_i2v(prompt, start_image, duration, seed):
    if seed == -1:
        seed = int(time.time() * 1000) % 2147483647
    if start_image is None:
        return None, "Please upload a starting frame image."

    # Save uploaded image and get base64 representation
    input_dir = os.path.join(os.path.dirname(__file__), "input")
    os.makedirs(input_dir, exist_ok=True)
    img_path = os.path.join(input_dir, "start_frame_i2v.png")
    if hasattr(start_image, "save"):
        start_image.save(img_path)
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    negative = "blurry, static, cartoon, low quality, distorted, fast motion, text, watermark, worst quality"
    wf = build_i2v_workflow(prompt, negative, img_b64, duration, seed)
    if wf is None:
        return None, "Workflow template 'wan_i2v' not found!"

    try:
        result = queue_prompt(wf)
        prompt_id = result["prompt_id"]
        entry = poll_until_done(prompt_id, max_wait=900)
        if entry is None:
            return None, "Timeout (15 min). Video generation is slow on 8GB VRAM."
        all_imgs = get_all_output_images(entry)
        if not all_imgs:
            return None, "No output frames. Check ComfyUI terminal."

        frame_bytes_list = []
        for img_info in all_imgs:
            data = get_image(img_info["filename"], img_info.get("subfolder", ""), img_info.get("type", "output"))
            if data:
                frame_bytes_list.append(data)

        if not frame_bytes_list:
            return None, "Failed to download output frames."

        output_video = os.path.join(os.path.dirname(__file__), "output", f"i2v_{prompt_id}.mp4")
        os.makedirs(os.path.dirname(output_video), exist_ok=True)
        frames_to_video(frame_bytes_list, output_video, fps=16)
        return output_video, f"Done! {len(frame_bytes_list)} frames, seed: {seed}"
    except Exception as e:
        return None, str(e)


def generate_char_to_video(char_prompt, char_neg, motion_prompt, motion_neg, width, height, seed):
    if seed == -1:
        seed = int(time.time() * 1000) % 2147483647

    wf = build_char_to_video_workflow(char_prompt, char_neg, motion_prompt, motion_neg, width, height, seed)
    if wf is None:
        return None, None, "Workflow template 'char_to_video' not found!"

    try:
        result = queue_prompt(wf)
        prompt_id = result["prompt_id"]
        # Full pipeline takes longer (two samplers)
        entry = poll_until_done(prompt_id, max_wait=1800)
        if entry is None:
            return None, None, "Timeout (30 min). Full pipeline is heavy on 8GB VRAM."
        all_imgs = get_all_output_images(entry)
        if not all_imgs:
            return None, None, "No output. Check ComfyUI terminal."

        # Videos are multi-frame batches (from Wan VAEDecode), single images are 1 frame
        frame_bytes_list = []
        for img_info in all_imgs:
            data = get_image(img_info["filename"], img_info.get("subfolder", ""), img_info.get("type", "output"))
            if data:
                frame_bytes_list.append(data)

        # The PreviewImage (character image) is typically a single frame
        # SaveImage outputs the full batch as individual PNGs
        if len(frame_bytes_list) <= 1:
            return None, None, "Only got 1 output frame. Video generation likely failed. Check ComfyUI."

        output_video = os.path.join(os.path.dirname(__file__), "output", f"char2vid_{prompt_id}.mp4")
        os.makedirs(os.path.dirname(output_video), exist_ok=True)
        frames_to_video(frame_bytes_list, output_video, fps=16)

        # First frame as character preview
        char_preview = frame_bytes_list[0] if frame_bytes_list else None
        return char_preview, output_video, f"Done! {len(frame_bytes_list)} frames, seed: {seed}"
    except Exception as e:
        return None, None, str(e)


# ============ UI Definition ============

def create_ui():
    prompt_lib = load_prompt_library()

    # Build prompt selector options
    prompt_choices = []
    for cat_key, cat_data in prompt_lib.get("categories", {}).items():
        for p in cat_data.get("prompts", []):
            label = f"[{cat_data['name_cn']}] {p['name_cn']}"
            prompt_choices.append((label, p["positive"], p["negative"]))

    with gr.Blocks(title="StyleForge - ComfyUI Creative Studio", theme=gr.themes.Soft()) as ui:
        gr.Markdown("""
        # StyleForge Creative Studio
        ### AI Image & Video Generation | Ideogram 4 + FLUX.2 + Qwen Image + Wan 2.1 | RTX 4060 Optimized
        """)

        with gr.Tabs():
            # ===== TAB 1: Text to Image =====
            with gr.Tab("文生图 Text-to-Image"):
                with gr.Row():
                    with gr.Column(scale=2):
                        txt2img_model = gr.Dropdown(
                            choices=["ideogram4", "flux2", "qwen_image"],
                            value="ideogram4",
                            label="模型 Model",
                            info="Ideogram 4: 排版设计/文字渲染 | FLUX.2: 写实摄影 | Qwen Image: 中文原生"
                        )
                        prompt = gr.Textbox(
                            label="提示词 Prompt",
                            placeholder="Describe what you want to see...",
                            lines=3,
                            value="masterpiece, best quality, 1girl, beautiful face, detailed eyes, photorealistic, soft lighting, portrait"
                        )
                        negative_prompt = gr.Textbox(
                            label="负面提示词 Negative Prompt",
                            placeholder="What to avoid...",
                            lines=2,
                            value="bad quality, worst quality, blurry, distorted face, deformed, ugly, extra fingers"
                        )
                        with gr.Row():
                            width = gr.Slider(512, 2048, value=512, step=64, label="Width")
                            height = gr.Slider(512, 2048, value=1024, step=64, label="Height")
                            seed = gr.Number(label="Seed (-1 = random)", value=-1, precision=0)
                        with gr.Row():
                            generate_btn = gr.Button("生成 Generate", variant="primary", size="lg")
                            use_prompt_btn = gr.Button("使用精选提示词", variant="secondary")

                    with gr.Column(scale=1):
                        output_image = gr.Image(label="生成结果", type="pil")
                        status_text = gr.Textbox(label="状态", value="Ready")

                # Prompt library selector
                with gr.Accordion("精选提示词库 Prompt Library", open=False):
                    prompt_selector = gr.Dropdown(
                        choices=[c[0] for c in prompt_choices],
                        label="选择提示词",
                        interactive=True
                    )

                def apply_prompt(selected):
                    for label, pos, neg in prompt_choices:
                        if label == selected:
                            return pos, neg
                    return "", ""

                prompt_selector.change(fn=apply_prompt, inputs=prompt_selector, outputs=[prompt, negative_prompt])

                generate_btn.click(
                    fn=generate_txt2img,
                    inputs=[prompt, negative_prompt, width, height, seed, txt2img_model],
                    outputs=[output_image, status_text]
                )

            # ===== TAB 2: Image to Image =====
            with gr.Tab("图生图 Image-to-Image"):
                with gr.Row():
                    with gr.Column(scale=2):
                        ref_image = gr.Image(label="参考图 Reference Image", type="pil")
                        img2img_prompt = gr.Textbox(
                            label="编辑指令 Edit Prompt",
                            lines=3,
                            value="Keep the same character, change background to cherry blossom garden, soft spring lighting"
                        )
                        img2img_neg = gr.Textbox(label="负面提示词", lines=2, value="bad quality, blurry, different character")
                        with gr.Row():
                            i2i_width = gr.Slider(512, 2048, value=512, step=64, label="Width")
                            i2i_height = gr.Slider(512, 2048, value=1024, step=64, label="Height")
                            i2i_seed = gr.Number(label="Seed", value=-1, precision=0)
                        img2img_btn = gr.Button("生成 Generate", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        img2img_output = gr.Image(label="生成结果")
                        img2img_status = gr.Textbox(label="状态", value="Ready")

                img2img_btn.click(
                    fn=generate_img2img,
                    inputs=[img2img_prompt, img2img_neg, ref_image, i2i_width, i2i_height, i2i_seed],
                    outputs=[img2img_output, img2img_status]
                )

            # ===== TAB 3: Text to Video =====
            with gr.Tab("文生视频 Text-to-Video"):
                gr.Markdown("""
                Wan 2.1 1.3B Text-to-Video | 480p 33 frames (~5s)
                """)
                with gr.Row():
                    with gr.Column(scale=2):
                        t2v_prompt = gr.Textbox(label="视频描述 Prompt", lines=3,
                            value="A single candle flame gently flickering in darkness, warm orange glow, macro cinematic shot, slow motion, peaceful atmosphere")
                        t2v_neg = gr.Textbox(label="负面提示词", lines=2, value="blurry, static, cartoon, fast motion")
                        with gr.Row():
                            t2v_duration = gr.Slider(2, 5, value=5, step=1, label="Duration (seconds)")
                            t2v_resolution = gr.Dropdown(["480p (832x480)", "720p (1280x720)"], value="480p (832x480)", label="Resolution")
                            t2v_seed = gr.Number(label="Seed", value=-1, precision=0)
                        t2v_btn = gr.Button("生成视频 Generate Video", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        t2v_output = gr.Video(label="生成视频")
                        t2v_status = gr.Textbox(label="状态", value="Ready")

                t2v_btn.click(
                    fn=generate_t2v,
                    inputs=[t2v_prompt, t2v_neg, t2v_duration, t2v_resolution, t2v_seed],
                    outputs=[t2v_output, t2v_status]
                )

            # ===== TAB 4: Image to Video =====
            with gr.Tab("图生视频 Image-to-Video"):
                gr.Markdown("""
                Upload an image as the starting frame. Wan 2.1 will animate it.
                """)
                with gr.Row():
                    with gr.Column(scale=2):
                        i2v_ref = gr.Image(label="起始帧 Starting Frame", type="pil")
                        i2v_prompt = gr.Textbox(label="动作描述 Motion Prompt", lines=2,
                            value="The person naturally smiles and turns head slightly, gentle hair movement, warm atmosphere")
                        with gr.Row():
                            i2v_duration = gr.Slider(2, 5, value=5, step=1, label="Duration")
                            i2v_seed = gr.Number(label="Seed", value=-1, precision=0)
                        i2v_btn = gr.Button("生成视频 Generate Video", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        i2v_output = gr.Video(label="生成视频")
                        i2v_status = gr.Textbox(label="状态", value="Ready")

                i2v_btn.click(
                    fn=generate_i2v,
                    inputs=[i2v_prompt, i2v_ref, i2v_duration, i2v_seed],
                    outputs=[i2v_output, i2v_status]
                )

            # ===== TAB 5: Character to Video (Full Pipeline) =====
            with gr.Tab("角色生视频 Character→Video"):
                gr.Markdown("""
                **Full Pipeline**: Text description → Generate character image → Animate into video
                """)
                with gr.Row():
                    with gr.Column(scale=2):
                        char_prompt = gr.Textbox(label="角色描述 Character Description", lines=3,
                            value="A stunning young woman with natural beauty, long black hair, elegant features, photorealistic portrait")
                        char_neg = gr.Textbox(label="图像负面提示词", lines=2,
                            value="bad quality, blurry, deformed, ugly, anime, cartoon, 3D render")
                        motion_prompt = gr.Textbox(label="动作描述 Motion Description", lines=2,
                            value="The person naturally smiles and gently turns their head, soft hair movement, warm atmosphere, slow motion")
                        motion_neg = gr.Textbox(label="视频负面提示词", lines=1,
                            value="blurry, static, cartoon, low quality, distorted, face distortion")
                        with gr.Row():
                            char_width = gr.Slider(512, 2048, value=1024, step=64, label="Image Width")
                            char_height = gr.Slider(512, 2048, value=1024, step=64, label="Image Height")
                        char_seed = gr.Number(label="Seed", value=-1, precision=0)
                        char_btn = gr.Button("生成角色并制作视频 Generate All", variant="primary", size="lg")

                    with gr.Column(scale=1):
                        char_image = gr.Image(label="1. 生成的角色图")
                        char_video = gr.Video(label="2. 最终视频")
                        char_status = gr.Textbox(label="状态", value="Ready")

                char_btn.click(
                    fn=generate_char_to_video,
                    inputs=[char_prompt, char_neg, motion_prompt, motion_neg, char_width, char_height, char_seed],
                    outputs=[char_image, char_video, char_status]
                )

        # Footer
        gr.Markdown("""
        ---
        **Models**: Ideogram 4 NF4 + FLUX.2 Klein 4B + Qwen Image FP8 + Wan 2.1 | **Hardware**: RTX 4060 8GB | **Resolution**: up to 2048px Image, 480p Video
        """)

    return ui


if __name__ == "__main__":
    ui = create_ui()
    print("\n" + "=" * 60)
    print("StyleForge WebUI starting at http://127.0.0.1:7860")
    print("Make sure ComfyUI is running at http://127.0.0.1:8188")
    print("=" * 60 + "\n")
    ui.launch(server_name="127.0.0.1", server_port=7860, share=False)
