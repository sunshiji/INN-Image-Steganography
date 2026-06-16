#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh - Environment verification script
#
# All packages (including GPU-only PyTorch) are installed via conda by
# environment.yml — no pip step is needed.  This script only verifies that
# the GPU is reachable and that the installed torch was built with CUDA support.
#
# Usage:
#   conda env create -f environment.yml   # install everything (one-time)
#   conda activate inn-stego
#   bash setup.sh                         # optional: verify GPU + torch
#   bash start.sh
#
# GPU detection uses nvidia-smi; nvcc / full CUDA toolkit is NOT required.
# ---------------------------------------------------------------------------
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "============================================================"
echo "  INN Steganography System - Setup"
echo "  Project: ${PROJ_DIR}"
echo "============================================================"

# --- 1. Verify conda env is active ---
if [ -n "${CONDA_DEFAULT_ENV}" ] && [ "${CONDA_DEFAULT_ENV}" != "base" ]; then
    echo "[1/2] Conda env: ${CONDA_DEFAULT_ENV}  (${CONDA_PREFIX})"
    PYTHON="${CONDA_PREFIX}/bin/python"
else
    echo "[ERROR] No active conda env detected." >&2
    echo "  Create and activate the inn-stego env first:" >&2
    echo "    conda env create -f ${PROJ_DIR}/environment.yml" >&2
    echo "    conda activate inn-stego" >&2
    exit 1
fi

# --- 2. Verify GPU and torch CUDA support ---
echo "[2/2] Checking GPU and torch..."
if ! command -v nvidia-smi >/dev/null 2>&1; then
    echo "[ERROR] nvidia-smi not found. An NVIDIA GPU driver is required." >&2
    exit 1
fi

# Parse CUDA version from the nvidia-smi header line (no nvcc required).
CUDA_VER=$(nvidia-smi 2>/dev/null \
    | grep -oP 'CUDA Version:\s*\K[\d.]+' | head -1 || true)
GPU_NAME=$(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null \
    | head -1 || true)
echo "  GPU  : ${GPU_NAME:-unknown}"
echo "  CUDA : ${CUDA_VER:-unknown}"

# Verify the installed torch was built with CUDA support.
TORCH_VER=$("${PYTHON}" -c "import torch; print(torch.__version__)" 2>/dev/null || echo "")
TORCH_CUDA=$("${PYTHON}" -c "import torch; print(torch.version.cuda or '')" 2>/dev/null || echo "")
if [ -z "${TORCH_VER}" ]; then
    echo "[ERROR] torch is not installed." >&2
    echo "  Recreate the conda env:" >&2
    echo "    conda env create -f ${PROJ_DIR}/environment.yml" >&2
    exit 1
elif [ -z "${TORCH_CUDA}" ]; then
    echo "[ERROR] torch ${TORCH_VER} has no CUDA support (CPU-only build)." >&2
    echo "  Recreate the conda env to get the GPU build:" >&2
    echo "    conda env remove -n ${CONDA_DEFAULT_ENV}" >&2
    echo "    conda env create -f ${PROJ_DIR}/environment.yml" >&2
    exit 1
else
    echo "  torch: ${TORCH_VER} (CUDA ${TORCH_CUDA}) ✓"
fi

echo ""
echo "============================================================"
echo "  Setup complete!"
echo ""
echo "  Start the service:"
echo "    bash ${PROJ_DIR}/start.sh"
echo ""
echo "  Access:"
echo "    http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1'):5000"
echo "============================================================"
