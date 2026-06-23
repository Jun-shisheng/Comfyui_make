"""Merge T5 text encoder shards into single safetensors file for ComfyUI."""
import json
import os
import safetensors.torch
import torch

SRC = "G:/ComfyUI/models/text_encoders/wan_t5/text_encoder"
DST = "G:/ComfyUI/models/text_encoders/wan_t5_umt5_xxl.safetensors"

print(f"Loading index from {SRC}")
with open(os.path.join(SRC, "model.safetensors.index.json")) as f:
    index = json.load(f)

weight_map = index["weight_map"]
shard_files = sorted(set(weight_map.values()))
print(f"Shards: {shard_files}")

merged = {}
for sf in shard_files:
    path = os.path.join(SRC, sf)
    print(f"  Loading {sf}...")
    with safetensors.safe_open(path, framework="pt") as f:
        st = {k: f.get_tensor(k) for k in f.keys()}
    merged.update(st)

print(f"Merged {len(merged)} tensors, saving to {DST}")
safetensors.torch.save_file(merged, DST)

# Verify
sz = os.path.getsize(DST) / 1e9
print(f"Done: {DST} ({sz:.1f}GB)")
