#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# stop.sh - Stop the INN Image Steganography backend server
#
# Usage:
#   bash stop.sh [PORT]
#   PORT defaults to the value of the PORT env var, or 5000.
#
# Finds any process listening on the given port and sends SIGTERM.
# If the process has not exited after 5 seconds, it is force-killed.
# ---------------------------------------------------------------------------

: "${PORT:=${1:-5000}}"

# --- Find PIDs bound to the port ---
PIDS=$(ss -tlnp 2>/dev/null | awk -F'pid=' "/0\.0\.0\.0:${PORT}|:::${PORT}/{print \$2}" | cut -d',' -f1)
if [ -z "${PIDS}" ] && command -v fuser >/dev/null 2>&1; then
    PIDS=$(fuser "${PORT}/tcp" 2>/dev/null | tr -s ' ' '\n' | grep -v '^$') || true
fi

if [ -z "${PIDS}" ]; then
    echo "[INFO] No process found on port ${PORT}. Nothing to stop."
    exit 0
fi

# --- Graceful stop (SIGTERM) ---
for PID in ${PIDS}; do
    echo "[INFO] Sending SIGTERM to PID ${PID} (port ${PORT})..."
    kill "${PID}" 2>/dev/null || true
done

# --- Wait up to 5 seconds ---
for attempt in 1 2 3 4 5; do
    sleep 1
    ss -tlnp 2>/dev/null | grep -qE "0\.0\.0\.0:${PORT}|:::${PORT}" || break
done

# --- Force-kill if still running ---
if ss -tlnp 2>/dev/null | grep -qE "0\.0\.0\.0:${PORT}|:::${PORT}"; then
    echo "[WARN] Port ${PORT} still in use; force-killing..."
    LIVE_PIDS=$(ss -tlnp 2>/dev/null | awk -F'pid=' "/0\.0\.0\.0:${PORT}|:::${PORT}/{print \$2}" | cut -d',' -f1)
    if [ -z "${LIVE_PIDS}" ] && command -v fuser >/dev/null 2>&1; then
        LIVE_PIDS=$(fuser "${PORT}/tcp" 2>/dev/null | tr -s ' ' '\n' | grep -v '^$') || true
    fi
    for PID in ${LIVE_PIDS}; do
        kill -9 "${PID}" 2>/dev/null || true
    done
    sleep 1
fi

if ss -tlnp 2>/dev/null | grep -qE "0\.0\.0\.0:${PORT}|:::${PORT}"; then
    echo "[ERROR] Failed to stop process on port ${PORT}." >&2
    exit 1
else
    echo "[INFO] Backend stopped (port ${PORT} is now free)."
fi
