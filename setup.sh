#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh - One-time environment setup script
#
# Recommended usage (new dedicated conda env):
#   conda env create -f environment.yml   # create inn-stego env (one-time)
#   conda activate inn-stego
#   bash setup.sh                         # installs torch with CUDA detection
#
# Alternative usage (existing conda env):
#   conda activate <env-name>
#   bash setup.sh
#
# Alternative usage (no conda, auto-creates ./venv/):
#   bash setup.sh
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
    if ! "${PYTHON}" --version >/dev/null 2>&1; then
        echo "[ERROR] Python not found. Create the conda env first:" >&2
        echo "  conda env create -f ${PROJ_DIR}/environment.yml" >&2
        exit 1
    fi
    PY_VER=$("${PYTHON}" -c "import sys; print('%d.%d' % sys.version_info[:2])")
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

# torch / torchvision: skip if already installed (preserves conda-installed pytorch)
TORCH_VER=$("${PYTHON}" -c "import torch; print(torch.__version__)" 2>/dev/null || echo "")
if [ -n "${TORCH_VER}" ]; then
    echo "  torch ${TORCH_VER} already present - skipping"
else
    # Detect CUDA version from nvcc or toolkit directory
    CUDA_VER=""
    if command -v nvcc >/dev/null 2>&1; then
        CUDA_VER=$(nvcc --version 2>/dev/null | grep -oP 'release \K[\d.]+' | head -1)
    elif [ -f /usr/local/cuda/version.txt ]; then
        CUDA_VER=$(grep -oP '[\d.]+' /usr/local/cuda/version.txt | head -1)
    fi

    if [ -n "${CUDA_VER}" ]; then
        CUDA_MAJOR=$(echo "${CUDA_VER}" | cut -d. -f1)
        CUDA_MINOR=$(echo "${CUDA_VER}" | cut -d. -f2)
        echo "  CUDA ${CUDA_VER} detected"
        if [ "${CUDA_MAJOR}" -ge 12 ]; then
            echo "  Installing torch 2.1.0 (CUDA 12.1)"
            "${PIP}" install "torch==2.1.0" "torchvision==0.16.0" \
                --index-url https://download.pytorch.org/whl/cu121 --quiet
        elif [ "${CUDA_MAJOR}" -eq 11 ] && [ "${CUDA_MINOR}" -ge 8 ]; then
            echo "  Installing torch 2.0.1 (CUDA 11.8)"
            "${PIP}" install "torch==2.0.1" "torchvision==0.15.2" \
                --index-url https://download.pytorch.org/whl/cu118 --quiet
        else
            # CUDA 11.3 – 11.7: use torch 1.12.1+cu113 (last release with cu113 builds)
            echo "  Installing torch 1.12.1 (CUDA 11.3)"
            "${PIP}" install "torch==1.12.1+cu113" "torchvision==0.13.1+cu113" \
                --extra-index-url https://download.pytorch.org/whl/cu113 --quiet
        fi
    else
        echo "  No CUDA detected - installing CPU PyTorch"
        "${PIP}" install torch torchvision --index-url https://download.pytorch.org/whl/cpu --quiet
    fi
fi

# Other dependencies (flask, flask-cors, gunicorn; no torch conflict)
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
