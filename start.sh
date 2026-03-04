#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# start.sh — 一键启动 INN 图像隐写系统（生产模式）
#
# 用法:
#   bash start.sh
#
# 可选环境变量:
#   PORT            监听端口（默认 5000）
#   SECRET_KEY      Session 密钥（生产环境必须设置！）
#   ADMIN_USERNAME  管理员用户名（默认 admin）
#   ADMIN_PASSWORD  管理员密码（默认 admin123，强烈建议修改！）
#
# 示例 — 自定义端口和密码:
#   PORT=8080 SECRET_KEY=my-secret ADMIN_PASSWORD=MyPass123 bash start.sh
# ---------------------------------------------------------------------------

set -e

cd "$(dirname "$0")/backend"

: "${PORT:=5000}"

echo "=================================================="
echo "  INN 图像隐写系统"
echo "  服务地址: http://0.0.0.0:${PORT}"
echo "  浏览器访问: http://$(hostname -I | awk '{print $1}'):${PORT}"
echo "=================================================="

exec gunicorn -w 2 -b "0.0.0.0:${PORT}" \
  --timeout 120 \
  --access-logfile - \
  app:app
