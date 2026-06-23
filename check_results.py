"""Check all test results."""
import json, urllib.request, os, glob

print("=" * 60)
print("ComfyUI Test Results - 2026-06-22")
print("=" * 60)

# Check recent temp files
temp_dir = "G:/ComfyUI/temp"
if os.path.exists(temp_dir):
    files = sorted(glob.glob(f"{temp_dir}/*.png"), key=os.path.getmtime, reverse=True)
    print(f"\nRecent output files ({len(files)} total):")
    for f in files[:5]:
        sz = os.path.getsize(f)
        print(f"  {os.path.basename(f)}: {sz} bytes")

# Check Wan T2V history
try:
    # Get recent history
    r = urllib.request.urlopen("http://127.0.0.1:8188/history", timeout=10)
    history = json.loads(r.read().decode())
    recent = list(history.items())[-3:]
    for pid, data in recent:
        outputs = data.get('outputs', {})
        status = data.get('status', {})
        print(f"\nPrompt {pid[:8]}...: completed={status.get('completed', False)}")
        for nid, out in outputs.items():
            for img in out.get('images', []):
                fn = img['filename']
                p = f"G:/ComfyUI/temp/{fn}"
                if os.path.exists(p):
                    print(f"  -> {fn} ({os.path.getsize(p)} bytes)")
except Exception as e:
    print(f"API check: {e}")
    # Check queue
    try:
        r = urllib.request.urlopen("http://127.0.0.1:8188/queue", timeout=10)
        q = json.loads(r.read().decode())
        print(f"Queue: {len(q.get('queue_running',[]))} running, {len(q.get('queue_pending',[]))} pending")
    except:
        print("ComfyUI may not be running")

# List all model files
print("\n=== Model Inventory ===")
for area in ['diffusion_models', 'text_encoders', 'vae']:
    d = f"G:/ComfyUI/models/{area}"
    if os.path.exists(d):
        total = 0
        for root, dirs, files in os.walk(d):
            for f in files:
                if f.endswith(('.safetensors', '.pth', '.ckpt')):
                    sz = os.path.getsize(os.path.join(root, f))
                    total += sz
        print(f"  {area}: {total/1e9:.1f}GB")
print(f"  TOTAL: ~46GB on G drive")
