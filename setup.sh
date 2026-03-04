#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh - One-time environment setup script
#
# Usage:
#   # With conda (recommended):
#   conda activate pris
#   bash setup.sh
#
#   # Without conda (creates ./venv/):
#   bash setup.sh
#
# The script installs only what is missing:
#   - In a conda env: installs flask, flask-cors, gunicorn into the env
#   - Without conda:  creates ./venv/ and installs all dependencies
#   - torch/torchvision are only installed if not already present
# ---------------------------------------------------------------------------
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${PROJ_DIR}/venv"

echo "============================================================"
echo "  INN Steganography System - Setup"
echo "  Project: ${PROJ_DIR}"
echo "============================================================"

# --- 1. Detect Python / pip ---
if [ -n "${CONDA_DEFAULT_ENV}" ] && [ "${CONDA_DEFAULT_ENV}" != "base" ]; then
    echo "[1/3] Conda env: ${CONDA_DEFAULT_ENV}  (${CONDA_PREFIX})"
    PYTHON="${CONDA_PREFIX}/bin/python"
    PIP="${CONDA_PREFIX}/bin/pip"
    USE_VENV=0
elif [ -d "${VENV_DIR}" ]; then
    echo "[1/3] Using existing venv: ${VENV_DIR}"
    source "${VENV_DIR}/bin/activate"
    PYTHON="${VENV_DIR}/bin/python"
    PIP="${VENV_DIR}/bin/pip"
    USE_VENV=1
else
    PYTHON="${PYTHON:-python3}"
    PY_VER=$("${PYTHON}" -c "import sys; print('%d.%d' % sys.version_info[:2])" 2>/dev/null || echo "?")
    echo "[1/3] Creating venv (Python ${PY_VER}): ${VENV_DIR}"
    "${PYTHON}" -m venv "${VENV_DIR}"
    source "${VENV_DIR}/bin/activate"
    PYTHON="${VENV_DIR}/bin/python"
    PIP="${VENV_DIR}/bin/pip"
    USE_VENV=1
fi

# --- 2. Upgrade pip ---
echo "[2/3] Upgrading pip..."
"${PIP}" install --upgrade pip --quiet

# --- 3. Install dependencies ---
echo "[3/3] Installing dependencies..."

# torch / torchvision: skip if already installed (avoid overwriting conda's pytorch)
if "${PYTHON}" -c "import torch" 2>/dev/null; then
    TORCH_VER=$("${PYTHON}" -c "import torch; print(torch.__version__)")
    echo "  torch ${TORCH_VER} already present - skipping"
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
    echo "  Installing PyTorch from: ${TORCH_INDEX}"
    "${PIP}" install torch torchvision --index-url "${TORCH_INDEX}" --quiet
else
    echo "  No CUDA - installing CPU PyTorch"
    "${PIP}" install torch torchvision --index-url https://download.pytorch.org/whl/cpu --quiet
fi

# Other dependencies (flask, flask-cors, gunicorn, etc.)
# requirements.txt does NOT include torch/torchvision to avoid version conflicts
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
echo "  Access:"
echo "    http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1'):5000"
echo "============================================================"
