"""Submit Wan T2V workflow to running ComfyUI."""
import json, urllib.request, sys

qwf = {
    '1': {'class_type': 'UNETLoader', 'inputs': {'unet_name': 'wan\\wan2.1_t2v_1.3b.safetensors', 'weight_dtype': 'default'}},
    '2': {'class_type': 'CLIPLoader', 'inputs': {'clip_name': 'wan_t5\\text_encoder\\model-00001-of-00003.safetensors', 'type': 'wan'}},
    '3': {'class_type': 'VAELoader', 'inputs': {'vae_name': 'wan\\Wan2.1_VAE.pth'}},
    '4': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': 'A beautiful sunset over the ocean, golden light on waves, cinematic, 4K'}},
    '5': {'class_type': 'CLIPTextEncode', 'inputs': {'clip': ['2', 0], 'text': 'blurry, static, cartoon, low quality, distorted'}},
    '6': {'class_type': 'WanImageToVideo', 'inputs': {'positive': ['4', 0], 'negative': ['5', 0], 'vae': ['3', 0], 'width': 832, 'height': 480, 'length': 81, 'batch_size': 1}},
    '7': {'class_type': 'KSampler', 'inputs': {'model': ['1', 0], 'positive': ['6', 0], 'negative': ['6', 1], 'latent_image': ['6', 2], 'seed': 42, 'steps': 20, 'cfg': 4.0, 'sampler_name': 'euler', 'scheduler': 'simple', 'denoise': 1.0}},
    '8': {'class_type': 'VAEDecode', 'inputs': {'samples': ['7', 0], 'vae': ['3', 0]}},
    '9': {'class_type': 'PreviewImage', 'inputs': {'images': ['8', 0]}},
}

data = json.dumps({'prompt': qwf}).encode()
req = urllib.request.Request('http://127.0.0.1:8188/prompt', data=data)
try:
    r = json.loads(urllib.request.urlopen(req, timeout=15).read())
    pid = r.get('prompt_id', '?')
    errs = r.get('node_errors', {})
    if errs:
        for nid, es in errs.items():
            for e in es.get('errors', []):
                msg = e.get('message', '?')
                detail = e.get('details', '?')
                print(f'Node {nid}: {msg}')
                if detail:
                    print(f'  {str(detail)[:300]}')
        sys.exit(1)
    else:
        print(f'SUBMITTED: {pid}')
        print('Wan T2V: 832x480, 81 frames, 20 steps')
except urllib.error.HTTPError as e:
    err = json.loads(e.read().decode())
    for nid, es in err.get('node_errors', {}).items():
        for e in es.get('errors', []):
            print(f'Node {nid}: {e.get("message", "?")}')
            print(f'  {str(e.get("details", ""))[:300]}')
    sys.exit(1)
