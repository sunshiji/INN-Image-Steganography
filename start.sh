#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start.sh - Start INN Image Steganography System (production mode)
#
# Prerequisites: run 'bash setup.sh' once first.
#
# Usage:
#   bash start.sh
#
# Environment variables:
#   PORT            Listening port (default: 5000)
#   SECRET_KEY      Session secret key (must set in production!)
#   ADMIN_USERNAME  Admin username (default: admin)
#   ADMIN_PASSWORD  Admin password (default: admin123)
#   WORKERS         Gunicorn worker count (default: 1)
#
# Example:
#   PORT=8080 SECRET_KEY=my-secret ADMIN_PASSWORD=MyPass123 bash start.sh
# ---------------------------------------------------------------------------
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${PROJ_DIR}/venv"
BACKEND_DIR="${PROJ_DIR}/backend"

: "${PORT:=5000}"

# --- Resolve gunicorn ---
# Priority: 1) project venv  2) CONDA_PREFIX env  3) PATH (conda activate / system)
if [ -f "${VENV_DIR}/bin/gunicorn" ]; then
    source "${VENV_DIR}/bin/activate"
    GUNICORN="${VENV_DIR}/bin/gunicorn"
elif [ -n "${CONDA_PREFIX}" ] && [ -f "${CONDA_PREFIX}/bin/gunicorn" ]; then
    GUNICORN="${CONDA_PREFIX}/bin/gunicorn"
elif command -v gunicorn >/dev/null 2>&1; then
    GUNICORN="$(command -v gunicorn)"
else
    echo "[ERROR] gunicorn not found." >&2
    echo "  Option A (conda): conda activate pris && bash setup.sh" >&2
    echo "  Option B (venv):  bash setup.sh" >&2
    exit 1
fi

echo "=================================================="
echo "  INN Image Steganography System"
echo "  Listen: http://0.0.0.0:${PORT}"
echo "  Access: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1'):${PORT}"
echo "=================================================="

cd "${BACKEND_DIR}"
exec "${GUNICORN}" \
    --config "${BACKEND_DIR}/gunicorn.conf.py" \
    app:app
