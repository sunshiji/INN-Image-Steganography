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

# --- Load ~/.inn-stego.env (lower priority than env vars already in the shell) ---
ENV_FILE="${HOME}/.inn-stego.env"
if [ -f "${ENV_FILE}" ]; then
    while read -r _line || [ -n "${_line}" ]; do
        case "${_line}" in ''|'#'*) continue ;; esac   # skip blank lines and comments
        case "${_line}" in *'='*) ;; *) continue ;; esac  # skip lines without '='
        _key="${_line%%=*}"
        _val="${_line#*=}"
        _key="${_key%% *}"                              # trim trailing whitespace from key
        [ -z "${_key}" ] && continue
        if [ -z "${!_key+x}" ]; then                   # only set if not already exported
            # Strip matching surrounding single or double quotes
            case "${_val}" in
                "'"*"'") _val="${_val#?}"; _val="${_val%?}" ;;
                '"'*'"') _val="${_val#?}"; _val="${_val%?}" ;;
            esac
            export "${_key}=${_val}"
        fi
    done < "${ENV_FILE}"
fi

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
    echo "  Option A (conda): conda activate inn-stego && bash setup.sh" >&2
    echo "  Option B (venv):  bash setup.sh" >&2
    exit 1
fi

# --- Stop any existing process already bound to the port ---
OLD_PIDS=$(ss -tlnp 2>/dev/null | awk -F'pid=' "/0\.0\.0\.0:${PORT}|:::${PORT}/{print \$2}" | cut -d',' -f1)
if [ -z "${OLD_PIDS}" ] && command -v fuser >/dev/null 2>&1; then
    OLD_PIDS=$(fuser "${PORT}/tcp" 2>/dev/null | tr -s ' ' '\n' | grep -v '^$') || true
fi
for OLD_PID in ${OLD_PIDS}; do
    echo "[INFO] Port ${PORT} is in use by PID ${OLD_PID}. Stopping it..."
    kill "${OLD_PID}" 2>/dev/null || true
done
if [ -n "${OLD_PIDS}" ]; then
    # Wait up to 5 seconds for the port to be released
    for attempt in 1 2 3 4 5; do
        sleep 1
        ss -tlnp 2>/dev/null | grep -qE "0\.0\.0\.0:${PORT}|:::${PORT}" || break
    done
    # Force-kill if port is still occupied
    if ss -tlnp 2>/dev/null | grep -qE "0\.0\.0\.0:${PORT}|:::${PORT}"; then
        echo "[WARN] Port ${PORT} still in use after SIGTERM; force-killing..."
        for OLD_PID in ${OLD_PIDS}; do
            kill -9 "${OLD_PID}" 2>/dev/null || true
        done
        sleep 1
    fi
fi

echo "=================================================="
echo "  INN Image Steganography System"
echo "  Listen: http://0.0.0.0:${PORT}"
echo "  Access: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '127.0.0.1'):${PORT}"
echo "  Admin:  ${ADMIN_USERNAME:-admin}"
echo "=================================================="

cd "${BACKEND_DIR}"
exec "${GUNICORN}" \
    --config "${BACKEND_DIR}/gunicorn.conf.py" \
    app:app
