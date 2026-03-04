#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# setup.sh — 一次性环境安装脚本
#
# 在项目目录下执行一次即可完成所有依赖安装。
#
# 用法:
#   cd /path/to/INN-Image-Steganography
#   bash setup.sh
#
# 脚本会:
#   1. 创建 Python 虚拟环境 (./venv)
#   2. 自动检测 CUDA，安装对应版本 PyTorch
#   3. 安装全部 Python 依赖
# ---------------------------------------------------------------------------

set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${PROJ_DIR}/venv"

echo "============================================================"
echo "  INN 图像隐写系统 — 环境安装"
echo "  项目路径: ${PROJ_DIR}"
echo "============================================================"

# ── 1. Python version check ──────────────────────────────────────────────────
PYTHON="${PYTHON:-python3}"
PY_VER=$("$PYTHON" -c "import sys; print('%d.%d' % sys.version_info[:2])")
echo "[1/3] Python 版本: ${PY_VER}"

# ── 2. Create virtual environment ────────────────────────────────────────────
if [ -d "${VENV_DIR}" ]; then
    echo "[2/3] 虚拟环境已存在: ${VENV_DIR}  (跳过创建)"
else
    echo "[2/3] 创建虚拟环境: ${VENV_DIR}"
    "$PYTHON" -m venv "${VENV_DIR}"
fi

PIP="${VENV_DIR}/bin/pip"
"$PIP" install --upgrade pip --quiet

# ── 3. Install PyTorch (GPU if available, else CPU) ──────────────────────────
echo "[3/3] 安装 Python 依赖 …"

if command -v nvcc &>/dev/null || [ -d /usr/local/cuda ]; then
    # Detect CUDA major version to pick the right torch index
    CUDA_VER=$(nvcc --version 2>/dev/null | grep -oP 'release \K[\d.]+' | head -1)
    CUDA_MAJOR=$(echo "$CUDA_VER" | cut -d. -f1)
    CUDA_MINOR=$(echo "$CUDA_VER" | cut -d. -f2)
    echo "    检测到 CUDA ${CUDA_VER}"

    if [ "${CUDA_MAJOR}" -ge 12 ]; then
        TORCH_INDEX="https://download.pytorch.org/whl/cu121"
    elif [ "${CUDA_MAJOR}" -eq 11 ] && [ "${CUDA_MINOR}" -ge 8 ]; then
        TORCH_INDEX="https://download.pytorch.org/whl/cu118"
    else
        TORCH_INDEX="https://download.pytorch.org/whl/cu117"
    fi
    echo "    PyTorch index: ${TORCH_INDEX}"
    "$PIP" install torch torchvision --index-url "${TORCH_INDEX}" --quiet
else
    echo "    未检测到 CUDA，安装 CPU 版 PyTorch"
    "$PIP" install torch torchvision --index-url https://download.pytorch.org/whl/cpu --quiet
fi

# Install remaining dependencies from requirements.txt
"$PIP" install -r "${PROJ_DIR}/backend/requirements.txt" --quiet

echo ""
echo "============================================================"
echo "  安装完成！"
echo ""
echo "  启动服务:"
echo "    bash ${PROJ_DIR}/start.sh"
echo ""
echo "  使用自定义密码启动:"
echo "    ADMIN_PASSWORD=YourPassword bash ${PROJ_DIR}/start.sh"
echo "============================================================"
