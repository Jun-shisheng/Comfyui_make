#!/bin/bash
# Download all models using aria2c via hf-mirror.com
# All files go to G:/ComfyUI/models/

ARIA2C="/e/TOOL/aria2/aria2-download/aria2-1.37.0-win-64bit-build1/aria2c"
MODELS_DIR="G:/ComfyUI/models"
MIRROR="https://hf-mirror.com"

# aria2c common options
ARIA2_OPTS="-x 4 -s 4 --file-allocation=none --console-log-level=notice --summary-interval=10"

echo "============================================"
echo "Downloading models to $MODELS_DIR"
echo "Mirror: $MIRROR"
echo "============================================"

# 1. Qwen Image FP8 (~8GB)
echo ""
echo "[1/4] Qwen Image FP8 (~8GB)"
mkdir -p "$MODELS_DIR/diffusion_models"
"$ARIA2C" $ARIA2_OPTS \
    -o "$MODELS_DIR/diffusion_models/qwen_image_fp8_e4m3fn.safetensors" \
    "$MIRROR/Qwen/Qwen-Image/resolve/main/qwen_image_fp8_e4m3fn.safetensors"

echo ""
echo "[2/4] Qwen 2.5 VL 7B Text Encoder (~14GB)"
mkdir -p "$MODELS_DIR/text_encoders"
"$ARIA2C" $ARIA2_OPTS \
    -o "$MODELS_DIR/text_encoders/qwen_2.5_vl_7b_fp8_scaled.safetensors" \
    "$MIRROR/Qwen/Qwen-Image/resolve/main/qwen_2.5_vl_7b_fp8_scaled.safetensors"

echo ""
echo "[3/4] Wan 2.1 T2V 1.3B (~2.6GB)"
mkdir -p "$MODELS_DIR/diffusion_models/wan"
"$ARIA2C" $ARIA2_OPTS \
    -o "$MODELS_DIR/diffusion_models/wan/diffusion_pytorch_model_t2v.safetensors" \
    "$MIRROR/Wan-AI/Wan2.1-T2V-1.3B/resolve/main/diffusion_pytorch_model.safetensors"

echo ""
echo "[4/4] Wan 2.1 I2V 1.3B (~2.6GB)"
"$ARIA2C" $ARIA2_OPTS \
    -o "$MODELS_DIR/diffusion_models/wan/diffusion_pytorch_model_i2v.safetensors" \
    "$MIRROR/Wan-AI/Wan2.1-I2V-1.3B/resolve/main/diffusion_pytorch_model.safetensors"

echo ""
echo "============================================"
echo "Core models done! Downloading VAE + configs..."
echo "============================================"

# Wan VAE
echo ""
echo "[5] Wan 2.1 VAE (~250MB)"
mkdir -p "$MODELS_DIR/vae/wan"
"$ARIA2C" $ARIA2_OPTS \
    -o "$MODELS_DIR/vae/wan/Wan2.1_VAE.pth" \
    "$MIRROR/Wan-AI/Wan2.1-T2V-1.3B/resolve/main/Wan2.1_VAE.pth"

# Wan config files
echo ""
echo "[6] Wan T2V config"
"$ARIA2C" $ARIA2_OPTS \
    -o "$MODELS_DIR/diffusion_models/wan/config_t2v.json" \
    "$MIRROR/Wan-AI/Wan2.1-T2V-1.3B/resolve/main/config.json"

echo ""
echo "[7] Wan I2V config"
"$ARIA2C" $ARIA2_OPTS \
    -o "$MODELS_DIR/diffusion_models/wan/config_i2v.json" \
    "$MIRROR/Wan-AI/Wan2.1-I2V-1.3B/resolve/main/config.json"

echo ""
echo "============================================"
echo "All downloads initiated. Check above for errors."
echo "============================================"
