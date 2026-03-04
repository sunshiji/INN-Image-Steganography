#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start.sh — 一键启动 INN 图像隐写系统（生产模式）
#
# 前提：已运行 bash setup.sh 完成安装。
#
# 用法:
#   bash start.sh
#
# 可选环境变量:
#   PORT            监听端口（默认 5000）
#   SECRET_KEY      Session 密钥（生产环境必须设置！）
#   ADMIN_USERNAME  管理员用户名（默认 admin）
#   ADMIN_PASSWORD  管理员密码（默认 admin123，强烈建议修改！）
#   WORKERS         gunicorn worker 数量（默认 1）
#
# 示例 — 自定义端口和密码:
#   PORT=8080 SECRET_KEY=my-secret ADMIN_PASSWORD=MyPass123 bash start.sh
# ---------------------------------------------------------------------------

set -e

PROJ_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${PROJ_DIR}/venv"
BACKEND_DIR="${PROJ_DIR}/backend"

: "${PORT:=5000}"

# ── Activate virtual environment if present ──────────────────────────────────
if [ -f "${VENV_DIR}/bin/activate" ]; then
    # shellcheck source=/dev/null
    source "${VENV_DIR}/bin/activate"
    GUNICORN="${VENV_DIR}/bin/gunicorn"
else
    # Fall back to system-wide gunicorn
    GUNICORN="$(command -v gunicorn)"
    if [ -z "$GUNICORN" ]; then
        echo "[ERROR] gunicorn not found. Run 'bash setup.sh' first." >&2
        exit 1
    fi
fi

echo "=================================================="
echo "  INN 图像隐写系统"
echo "  服务地址: http://0.0.0.0:${PORT}"
echo "  浏览器访问: http://$(hostname -I 2>/dev/null | awk '{print $1}' || echo '10.109.118.166'):${PORT}"
echo "=================================================="

cd "${BACKEND_DIR}"
exec "$GUNICORN" \
    --config "${BACKEND_DIR}/gunicorn.conf.py" \
    app:app
