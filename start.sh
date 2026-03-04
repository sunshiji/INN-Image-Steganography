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

# --- Resolve gunicorn path ---
if [ -f "${VENV_DIR}/bin/gunicorn" ]; then
    GUNICORN="${VENV_DIR}/bin/gunicorn"
    source "${VENV_DIR}/bin/activate"
elif command -v gunicorn >/dev/null 2>&1; then
    # Covers: conda env, system install
    GUNICORN="$(command -v gunicorn)"
else
    echo "[ERROR] gunicorn not found. Run 'bash setup.sh' first." >&2
    exit 1
fi

SERVER_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1')
echo "=================================================="
echo "  INN Image Steganography System"
echo "  Listen: http://0.0.0.0:${PORT}"
echo "  Access: http://${SERVER_IP}:${PORT}"
echo "=================================================="

cd "${BACKEND_DIR}"
exec "${GUNICORN}" \
    --config "${BACKEND_DIR}/gunicorn.conf.py" \
    app:app
