"""
SQLite persistence layer for INN Image Steganography.

Uses Python's built-in sqlite3 module — no external dependencies required.
The database file is created automatically on first use.

Environment variables
---------------------
SQLITE_DB_PATH   path to the SQLite database file
                 (default: ~/.inn-stego-data.db)
"""

import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DB_PATH = os.environ.get(
    "SQLITE_DB_PATH",
    os.path.join(os.path.expanduser("~"), ".inn-stego-data.db"),
)

_SESSION_TTL = 600  # seconds — must match app.py's _SESSION_TTL

# ---------------------------------------------------------------------------
# Thread safety
# ---------------------------------------------------------------------------

# SQLite connections are not thread-safe in multi-threaded mode unless we use
# check_same_thread=False with an explicit lock.  We use a module-level lock
# so all calls serialise cleanly under gunicorn's sync worker model.
_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,
    role          TEXT    NOT NULL DEFAULT 'user',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS stego_images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL,
    image_type  TEXT    NOT NULL,
    filename    TEXT    NOT NULL DEFAULT 'image.png',
    width       INTEGER,
    height      INTEGER,
    format      TEXT    NOT NULL DEFAULT 'PNG',
    data_b64    TEXT    NOT NULL,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS encode_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    task_token        TEXT    NOT NULL UNIQUE,
    username          TEXT    NOT NULL,
    cover_image_id    INTEGER DEFAULT NULL,
    secret_image_id   INTEGER DEFAULT NULL,
    stego_image_id    INTEGER DEFAULT NULL,
    recovery_image_id INTEGER DEFAULT NULL,
    psnr_cover_stego  REAL    DEFAULT NULL,
    ssim_cover_stego  REAL    DEFAULT NULL,
    model_type        TEXT    NOT NULL DEFAULT 'HiNet',
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at        TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS decode_tasks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    username           TEXT    NOT NULL,
    stego_image_id     INTEGER DEFAULT NULL,
    recovered_image_id INTEGER DEFAULT NULL,
    decode_mode        TEXT    NOT NULL DEFAULT 'approximate',
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);
"""


def _init_db() -> None:
    """Create tables if they do not yet exist."""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.executescript(_SCHEMA)
        conn.commit()
        conn.close()
    except Exception as exc:
        print(f"[DB] SQLite init failed: {exc}", flush=True)


_init_db()

# ---------------------------------------------------------------------------
# Connection helper
# ---------------------------------------------------------------------------


@contextmanager
def _cursor():
    """Context manager: open a connection, yield a cursor, commit/rollback."""
    with _lock:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        try:
            cur = conn.cursor()
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def is_available() -> bool:
    """Return True — SQLite is always available."""
    try:
        with _cursor() as cur:
            cur.execute("SELECT 1")
        return True
    except Exception as exc:
        print(f"[DB] SQLite not available: {exc}", flush=True)
        return False


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------


def session_store(token: str, stego_image: str, stego_key: str,
                  recovery_image: str) -> bool:
    """
    Persist a server-side session entry to SQLite.

    Returns True on success, False on error.
    """
    try:
        expires_at = time.strftime(
            "%Y-%m-%d %H:%M:%S",
            time.gmtime(time.time() + _SESSION_TTL),
        )
        with _cursor() as cur:
            cur.execute(
                """
                INSERT OR REPLACE INTO encode_tasks
                    (task_token, username, psnr_cover_stego, ssim_cover_stego,
                     model_type, created_at, expires_at)
                VALUES (?, '__session__', NULL, NULL, 'HiNet', datetime('now'), ?)
                """,
                (token, expires_at),
            )
        return True
    except Exception as exc:
        print(f"[DB] session_store failed: {exc}", flush=True)
        return False


def session_load(token: str) -> Optional[dict]:
    """
    Retrieve a session by token from SQLite.

    Returns dict with keys stego_image, stego_key, recovery_image
    or None if not found / expired.
    """
    try:
        with _cursor() as cur:
            cur.execute(
                """
                SELECT stego_image_id, recovery_image_id FROM encode_tasks
                WHERE task_token = ?
                  AND expires_at > datetime('now')
                """,
                (token,),
            )
            row = cur.fetchone()
            if row is None:
                return None
            result = {}
            for key, col in (
                ("stego_image",    "stego_image_id"),
                ("recovery_image", "recovery_image_id"),
            ):
                img_id = row[col]
                if img_id:
                    cur.execute(
                        "SELECT data_b64 FROM stego_images WHERE id = ?",
                        (img_id,),
                    )
                    r = cur.fetchone()
                    result[key] = r["data_b64"] if r else ""
                else:
                    result[key] = ""
            result["stego_key"] = ""
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
    """Insert an image into stego_images and return its new id."""
    try:
        with _cursor() as cur:
            cur.execute(
                """
                INSERT INTO stego_images
                    (username, image_type, filename, width, height, data_b64)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (username, image_type, filename, width, height, data_b64),
            )
            return cur.lastrowid
    except Exception as exc:
        print(f"[DB] save_image failed: {exc}", flush=True)
        return None


def get_image_b64(image_id: int) -> Optional[str]:
    """Return the base64 image data for a given image_id, or None."""
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT data_b64 FROM stego_images WHERE id = ?", (image_id,)
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
    Persist a complete encode task (images + metrics) to SQLite.

    Returns the new encode_tasks.id or None on failure.
    """
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
                INSERT OR REPLACE INTO encode_tasks
                    (task_token, username, cover_image_id, secret_image_id,
                     stego_image_id, recovery_image_id,
                     psnr_cover_stego, ssim_cover_stego, model_type,
                     created_at, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), ?)
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
    """Persist a decode task to SQLite.  Returns decode_tasks.id or None."""
    try:
        stego_id     = save_image(username, "stego",    stego_b64,     "stego.png")
        recovered_id = save_image(username, "recovery", recovered_b64, "recovery.png")
        with _cursor() as cur:
            cur.execute(
                """
                INSERT INTO decode_tasks
                    (username, stego_image_id, recovered_image_id,
                     decode_mode, created_at)
                VALUES (?, ?, ?, ?, datetime('now'))
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
    try:
        rows = []
        with _cursor() as cur:
            cur.execute(
                """
                SELECT 'encode' AS type, id, created_at,
                       psnr_cover_stego AS psnr,
                       ssim_cover_stego AS ssim,
                       NULL             AS mode,
                       stego_image_id,
                       recovery_image_id,
                       task_token       AS token
                FROM encode_tasks
                WHERE username = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (username, limit),
            )
            rows += [dict(r) for r in cur.fetchall()]

            cur.execute(
                """
                SELECT 'decode' AS type, id, created_at,
                       NULL     AS psnr,
                       NULL     AS ssim,
                       decode_mode AS mode,
                       stego_image_id,
                       recovered_image_id AS recovery_image_id,
                       NULL     AS token
                FROM decode_tasks
                WHERE username = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (username, limit),
            )
            rows += [dict(r) for r in cur.fetchall()]

        rows.sort(key=lambda r: r.get("created_at") or "", reverse=True)
        return rows[:limit]
    except Exception as exc:
        print(f"[DB] get_task_history failed: {exc}", flush=True)
        return []


# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------


def purge_expired() -> None:
    """Remove expired encode tasks and orphaned images from the database."""
    try:
        with _cursor() as cur:
            cur.execute(
                "DELETE FROM encode_tasks WHERE expires_at < datetime('now')"
            )
            cur.execute(
                """
                DELETE FROM stego_images
                WHERE id NOT IN (
                    SELECT cover_image_id    FROM encode_tasks
                     WHERE cover_image_id    IS NOT NULL
                    UNION ALL
                    SELECT secret_image_id   FROM encode_tasks
                     WHERE secret_image_id   IS NOT NULL
                    UNION ALL
                    SELECT stego_image_id    FROM encode_tasks
                     WHERE stego_image_id    IS NOT NULL
                    UNION ALL
                    SELECT recovery_image_id FROM encode_tasks
                     WHERE recovery_image_id IS NOT NULL
                    UNION ALL
                    SELECT stego_image_id    FROM decode_tasks
                     WHERE stego_image_id    IS NOT NULL
                    UNION ALL
                    SELECT recovered_image_id FROM decode_tasks
                     WHERE recovered_image_id IS NOT NULL
                )
                """
            )
    except Exception as exc:
        print(f"[DB] purge_expired failed: {exc}", flush=True)
