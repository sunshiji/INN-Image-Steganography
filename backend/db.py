"""
Optional MySQL 8 persistence layer for INN Image Steganography.

Activated only when MYSQL_PASSWORD (or MYSQL_DSN) is set in the environment.
Falls back gracefully to the in-memory store when MySQL is unavailable so the
application keeps working without a database server.

Environment variables
---------------------
MYSQL_HOST      database host           (default: localhost)
MYSQL_PORT      database port           (default: 3306)
MYSQL_USER      database user           (default: inn_stego)
MYSQL_PASSWORD  database password       (required to activate MySQL)
MYSQL_DB        database name           (default: inn_stego_db)

Schema
------
See backend/schema.sql for the full DDL.
"""

import os
import time
import threading
from contextlib import contextmanager
from typing import Optional

# PyMySQL is an optional dependency; import lazily so the app starts without it.
try:
    import pymysql
    import pymysql.cursors
    _PYMYSQL_AVAILABLE = True
except ImportError:
    _PYMYSQL_AVAILABLE = False

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MYSQL_HOST     = os.environ.get("MYSQL_HOST", "localhost")
MYSQL_PORT     = int(os.environ.get("MYSQL_PORT", "3306"))
MYSQL_USER     = os.environ.get("MYSQL_USER", "inn_stego")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD", "")
MYSQL_DB       = os.environ.get("MYSQL_DB", "inn_stego_db")

# MySQL is only activated when a password is explicitly provided.
MYSQL_ENABLED = bool(_PYMYSQL_AVAILABLE and MYSQL_PASSWORD)

_SESSION_TTL = 600  # seconds — must match app.py's _SESSION_TTL

# ---------------------------------------------------------------------------
# Connection pool (simple thread-local connection per worker)
# ---------------------------------------------------------------------------

_local = threading.local()


def _get_connection():
    """Return a cached per-thread PyMySQL connection, reconnecting if needed."""
    conn = getattr(_local, "conn", None)
    if conn is None or not conn.open:
        conn = pymysql.connect(
            host=MYSQL_HOST,
            port=MYSQL_PORT,
            user=MYSQL_USER,
            password=MYSQL_PASSWORD,
            database=MYSQL_DB,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=False,
            connect_timeout=5,
        )
        _local.conn = conn
    return conn


@contextmanager
def _cursor():
    """Context manager: yield a cursor and commit/rollback on exit."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def is_available() -> bool:
    """Return True if MySQL is configured and reachable."""
    if not MYSQL_ENABLED:
        return False
    try:
        with _cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as exc:
        print(f"[DB] MySQL not available: {exc}", flush=True)
        return False


# ---------------------------------------------------------------------------
# Session store (mirrors the in-memory _SESSION_STORE in app.py)
# ---------------------------------------------------------------------------

def session_store(token: str, stego_image: str, stego_key: str,
                  recovery_image: str) -> bool:
    """
    Persist a server-side session entry to MySQL.

    This is called from api_session_store() in addition to (not instead of)
    the in-memory dict so the data survives worker restarts.

    Returns True on success, False if MySQL is unavailable.
    """
    if not MYSQL_ENABLED:
        return False
    try:
        expires_at = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.gmtime(time.time() + _SESSION_TTL),
        )
        with _cursor() as cur:
            cur.execute(
                """
                INSERT INTO encode_tasks
                    (task_token, username, psnr_cover_stego, ssim_cover_stego,
                     model_type, created_at, expires_at)
                VALUES (%s, %s, NULL, NULL, 'HiNet', NOW(), %s)
                ON DUPLICATE KEY UPDATE
                    expires_at = VALUES(expires_at)
                """,
                (token, "__session__", expires_at),
            )
        return True
    except Exception as exc:
        print(f"[DB] session_store failed: {exc}", flush=True)
        return False


def session_load(token: str) -> Optional[dict]:
    """
    Retrieve a session by token from MySQL.

    Returns dict with keys stego_image, stego_key, recovery_image
    or None if not found / expired.
    """
    if not MYSQL_ENABLED:
        return None
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT stego_image_id, recovery_image_id FROM encode_tasks "
                "WHERE task_token = %s AND expires_at > NOW()",
                (token,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            # Retrieve image data
            result = {}
            for key, col in (
                ("stego_image",    "stego_image_id"),
                ("recovery_image", "recovery_image_id"),
            ):
                img_id = row.get(col)
                if img_id:
                    cur.execute(
                        "SELECT data_b64 FROM stego_images WHERE id = %s",
                        (img_id,),
                    )
                    r = cur.fetchone()
                    result[key] = r["data_b64"] if r else ""
                else:
                    result[key] = ""
            result["stego_key"] = ""  # stego_key no longer stored in DB
            return result
    except Exception as exc:
        print(f"[DB] session_load failed: {exc}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Image persistence helpers
# ---------------------------------------------------------------------------

def save_image(username: str, image_type: str, data_b64: str,
               filename: str = "image.png", width: int = None,
               height: int = None) -> Optional[int]:
    """
    Insert an image into stego_images and return its new id.

    Returns None if MySQL is unavailable.
    """
    if not MYSQL_ENABLED:
        return None
    try:
        with _cursor() as cur:
            cur.execute(
                """
                INSERT INTO stego_images
                    (username, image_type, filename, width, height, data_b64)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (username, image_type, filename, width, height, data_b64),
            )
            return cur.lastrowid
    except Exception as exc:
        print(f"[DB] save_image failed: {exc}", flush=True)
        return None


def get_image_b64(image_id: int) -> Optional[str]:
    """Return the base64 image data for a given image_id, or None."""
    if not MYSQL_ENABLED:
        return None
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT data_b64 FROM stego_images WHERE id = %s", (image_id,)
            )
            row = cur.fetchone()
            return row["data_b64"] if row else None
    except Exception as exc:
        print(f"[DB] get_image_b64 failed: {exc}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Task record helpers
# ---------------------------------------------------------------------------

def record_encode_task(
    token: str,
    username: str,
    cover_b64: str,
    secret_b64: str,
    stego_b64: str,
    recovery_b64: str,
    psnr: float,
    ssim: float,
    model_type: str = "HiNet",
) -> Optional[int]:
    """
    Persist a complete encode task (images + metrics) to MySQL.

    Returns the new encode_tasks.id or None on failure.
    """
    if not MYSQL_ENABLED:
        return None
    try:
        cover_id    = save_image(username, "cover",    cover_b64,    "cover.png")
        secret_id   = save_image(username, "secret",   secret_b64,   "secret.png")
        stego_id    = save_image(username, "stego",    stego_b64,    "stego.png")
        recovery_id = save_image(username, "recovery", recovery_b64, "recovery.png")
        expires_at  = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.gmtime(time.time() + _SESSION_TTL),
        )
        with _cursor() as cur:
            cur.execute(
                """
                INSERT INTO encode_tasks
                    (task_token, username, cover_image_id, secret_image_id,
                     stego_image_id, recovery_image_id,
                     psnr_cover_stego, ssim_cover_stego, model_type,
                     created_at, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
                ON DUPLICATE KEY UPDATE
                    stego_image_id    = VALUES(stego_image_id),
                    recovery_image_id = VALUES(recovery_image_id),
                    psnr_cover_stego  = VALUES(psnr_cover_stego),
                    ssim_cover_stego  = VALUES(ssim_cover_stego),
                    expires_at        = VALUES(expires_at)
                """,
                (
                    token, username,
                    cover_id, secret_id, stego_id, recovery_id,
                    psnr, ssim, model_type, expires_at,
                ),
            )
            return cur.lastrowid
    except Exception as exc:
        print(f"[DB] record_encode_task failed: {exc}", flush=True)
        return None


def record_decode_task(
    username: str,
    stego_b64: str,
    recovered_b64: str,
    mode: str,
) -> Optional[int]:
    """
    Persist a decode task to MySQL.  Returns decode_tasks.id or None.
    """
    if not MYSQL_ENABLED:
        return None
    try:
        stego_id     = save_image(username, "stego",    stego_b64,     "stego.png")
        recovered_id = save_image(username, "recovery", recovered_b64, "recovery.png")
        with _cursor() as cur:
            cur.execute(
                """
                INSERT INTO decode_tasks
                    (username, stego_image_id, recovered_image_id,
                     decode_mode, created_at)
                VALUES (%s, %s, %s, %s, NOW())
                """,
                (username, stego_id, recovered_id, mode),
            )
            return cur.lastrowid
    except Exception as exc:
        print(f"[DB] record_decode_task failed: {exc}", flush=True)
        return None


# ---------------------------------------------------------------------------
# Task history
# ---------------------------------------------------------------------------

def get_task_history(username: str, limit: int = 20) -> list:
    """
    Return recent encode + decode tasks for *username*, newest first.

    Each entry is a dict with keys:
        type, id, created_at, psnr, ssim, mode,
        stego_image_id, recovery_image_id
    """
    if not MYSQL_ENABLED:
        return []
    try:
        rows = []
        with _cursor() as cur:
            # Encode tasks
            cur.execute(
                """
                SELECT 'encode' AS type, id, created_at,
                       psnr_cover_stego AS psnr,
                       ssim_cover_stego AS ssim,
                       NULL            AS mode,
                       stego_image_id, recovery_image_id,
                       task_token      AS token
                FROM encode_tasks
                WHERE username = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (username, limit),
            )
            rows += cur.fetchall()
            # Decode tasks
            cur.execute(
                """
                SELECT 'decode' AS type, id, created_at,
                       NULL     AS psnr,
                       NULL     AS ssim,
                       decode_mode AS mode,
                       stego_image_id, recovered_image_id AS recovery_image_id,
                       NULL     AS token
                FROM decode_tasks
                WHERE username = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (username, limit),
            )
            rows += cur.fetchall()

        # Sort combined list by created_at descending and cap at limit
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        # Convert datetime objects to ISO strings for JSON serialization
        for r in rows:
            if hasattr(r.get("created_at"), "isoformat"):
                r["created_at"] = r["created_at"].isoformat()
        return rows[:limit]
    except Exception as exc:
        print(f"[DB] get_task_history failed: {exc}", flush=True)
        return []


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

def purge_expired() -> None:
    """Call the MySQL stored procedure that removes expired tasks + orphan images."""
    if not MYSQL_ENABLED:
        return
    try:
        with _cursor() as cur:
            cur.execute("CALL purge_expired_tasks()")
    except Exception as exc:
        print(f"[DB] purge_expired failed: {exc}", flush=True)
