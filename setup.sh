#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh - yi ci xing huan jing an zhuang jiao ben
#
# Yong fa:
#   cd /path/to/INN-Image-Steganography
#   bash setup.sh
#
# Zhi chi liang zhong mo shi:
#   - Conda huan jing (CONDA_DEFAULT_ENV yi she zhi): zhi jie an zhuang dao dang qian conda huan jing
#   - Fei conda huan jing: chuang jian ./venv/ bing an zhuang
# ---------------------------------------------------------------------------
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${PROJ_DIR}/venv"

echo "============================================================"
echo "  INN Steganography System - Setup"
echo "  Project: ${PROJ_DIR}"
echo "============================================================"

# --- 1. Detect Python interpreter ---
if [ -n "${CONDA_DEFAULT_ENV}" ] && [ "${CONDA_DEFAULT_ENV}" != "base" ]; then
    echo "[1/3] Conda env detected: ${CONDA_DEFAULT_ENV}"
    PYTHON="python"
    PIP="pip"
    USE_VENV=0
elif [ -d "${VENV_DIR}" ]; then
    echo "[1/3] Existing venv detected: ${VENV_DIR}"
    source "${VENV_DIR}/bin/activate"
    PYTHON="${VENV_DIR}/bin/python"
    PIP="${VENV_DIR}/bin/pip"
    USE_VENV=1
else
    PYTHON="${PYTHON:-python3}"
    PY_VER=$("${PYTHON}" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || echo "unknown")
    echo "[1/3] Python version: ${PY_VER} (will create venv)"
    "${PYTHON}" -m venv "${VENV_DIR}"
    source "${VENV_DIR}/bin/activate"
    PYTHON="${VENV_DIR}/bin/python"
    PIP="${VENV_DIR}/bin/pip"
    USE_VENV=1
fi

# --- 2. Upgrade pip ---
echo "[2/3] Upgrading pip..."
"${PIP}" install --upgrade pip --quiet

# --- 3. Install PyTorch (GPU if available, else CPU) ---
echo "[3/3] Installing dependencies..."

# Check if torch is already installed
if "${PYTHON}" -c "import torch" 2>/dev/null; then
    TORCH_VER=$("${PYTHON}" -c "import torch; print(torch.__version__)")
    echo "  torch already installed: ${TORCH_VER} (skipping)"
elif command -v nvcc >/dev/null 2>&1 || [ -d /usr/local/cuda ]; then
    CUDA_VER=$(nvcc --version 2>/dev/null | grep -oP 'release \K[\d.]+' | head -1)
    CUDA_MAJOR=$(echo "${CUDA_VER}" | cut -d. -f1)
    CUDA_MINOR=$(echo "${CUDA_VER}" | cut -d. -f2)
    echo "  CUDA ${CUDA_VER} detected"
    if [ "${CUDA_MAJOR}" -ge 12 ]; then
        TORCH_INDEX="https://download.pytorch.org/whl/cu121"
    elif [ "${CUDA_MAJOR}" -eq 11 ] && [ "${CUDA_MINOR}" -ge 8 ]; then
        TORCH_INDEX="https://download.pytorch.org/whl/cu118"
    else
        TORCH_INDEX="https://download.pytorch.org/whl/cu117"
    fi
    echo "  PyTorch index: ${TORCH_INDEX}"
    "${PIP}" install torch torchvision --index-url "${TORCH_INDEX}" --quiet
else
    echo "  No CUDA detected, installing CPU PyTorch"
    "${PIP}" install torch torchvision --index-url https://download.pytorch.org/whl/cpu --quiet
fi

# Install remaining dependencies
"${PIP}" install -r "${PROJ_DIR}/backend/requirements.txt" --quiet

echo ""
echo "============================================================"
echo "  Setup complete!"
if [ "${USE_VENV}" -eq 1 ]; then
    echo "  Venv: ${VENV_DIR}"
fi
echo ""
echo "  Start the service:"
echo "    bash ${PROJ_DIR}/start.sh"
echo ""
echo "  Browser access:"
echo "    http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1'):5000"
echo "============================================================"
