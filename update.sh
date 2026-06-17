#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# update.sh - Pull the latest code and restart the backend service
#
# Usage:
#   bash update.sh           # update from current branch (origin)
#   bash update.sh main      # update from a specific branch
#
# The script auto-detects how the service is running and restarts it:
#   1. systemd user unit  (inn-stego.service)
#   2. start.sh           (direct / nohup)
# ---------------------------------------------------------------------------
set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
BRANCH="${1:-}"

echo "=================================================="
echo "  INN Image Steganography – Code Update"
echo "  Directory: ${PROJ_DIR}"
echo "=================================================="

# ── 1. Pull latest code ────────────────────────────────
cd "${PROJ_DIR}"

if [ -n "${BRANCH}" ]; then
    echo "[INFO] Fetching branch '${BRANCH}' from origin..."
    git fetch origin "${BRANCH}"
    git checkout "${BRANCH}"
    git merge --ff-only "origin/${BRANCH}"
else
    echo "[INFO] Pulling latest code from origin..."
    git pull --ff-only
fi

echo "[INFO] Code updated."

# ── 2. Restart the backend ─────────────────────────────
if systemctl --user is-active inn-stego >/dev/null 2>&1; then
    echo "[INFO] Restarting systemd user service 'inn-stego'..."
    systemctl --user restart inn-stego
    echo "[INFO] Service restarted."
    systemctl --user status inn-stego --no-pager | head -10
else
    echo "[INFO] systemd service not active. Restarting via stop.sh + start.sh..."
    bash "${PROJ_DIR}/stop.sh"
    echo "[INFO] Starting backend in the background (nohup)..."
    LOG="${HOME}/inn-stego.log"
    nohup bash "${PROJ_DIR}/start.sh" >> "${LOG}" 2>&1 &
    echo "[INFO] Backend started (PID $!). Logs: ${LOG}"
fi

echo "=================================================="
echo "  Update complete."
echo "=================================================="
