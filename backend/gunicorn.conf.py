# ---------------------------------------------------------------------------
# gunicorn.conf.py — Gunicorn 生产配置
#
# 位于 backend/ 目录下，由 start.sh 自动加载。
# 所有参数均可被命令行选项覆盖。
# ---------------------------------------------------------------------------

import os
import multiprocessing

# ── Binding ──────────────────────────────────────────────────────────────────
bind = f"0.0.0.0:{os.environ.get('PORT', '5000')}"

# ── Workers ──────────────────────────────────────────────────────────────────
# INN 模型占用显存/内存较大，建议每 GPU 1 个 worker。
# CPU 模式可适当增加，但注意内存用量。
workers = int(os.environ.get("WORKERS", "1"))
worker_class = "sync"

# ── Timeouts ─────────────────────────────────────────────────────────────────
# INN 推理（尤其 CPU 模式）耗时较长，设置较大超时。
timeout = int(os.environ.get("TIMEOUT", "180"))
graceful_timeout = 30
keepalive = 5

# ── Request limits ───────────────────────────────────────────────────────────
# 图像上传体积上限：50 MB
limit_request_line = 8190
limit_request_fields = 200

# ── Logging ──────────────────────────────────────────────────────────────────
accesslog = "-"          # 输出到 stdout
errorlog  = "-"          # 输出到 stderr
loglevel  = os.environ.get("LOG_LEVEL", "info")
access_log_format = '%(h)s "%(r)s" %(s)s %(b)s %(D)sμs'

# ── Process name ─────────────────────────────────────────────────────────────
proc_name = "inn-stego"
