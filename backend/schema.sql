-- =============================================================================
-- INN Image Steganography System — SQLite database schema
--
-- This file is for reference only.
-- The application (backend/db.py) creates the tables automatically on startup
-- using Python's built-in sqlite3 module — no manual setup is needed.
--
-- To inspect or pre-create the database manually:
--   sqlite3 ~/.inn-stego-data.db < backend/schema.sql
--
-- The database file path is controlled by the SQLITE_DB_PATH environment
-- variable (default: ~/.inn-stego-data.db).
-- =============================================================================

-- ── users ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT    NOT NULL UNIQUE,
    password_hash TEXT    NOT NULL,       -- pbkdf2_hmac SHA-256: salt$hex
    role          TEXT    NOT NULL DEFAULT 'user',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- ── stego_images ──────────────────────────────────────────────────────────────
-- Stores every image produced or consumed by the system.
-- data_b64 holds the raw PNG/JPEG as a base64 string (TEXT: up to 1 GB).
CREATE TABLE IF NOT EXISTS stego_images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    TEXT    NOT NULL,   -- owner / uploader username
    image_type  TEXT    NOT NULL,   -- cover | secret | encrypted | stego | recovery
    filename    TEXT    NOT NULL DEFAULT 'image.png',
    width       INTEGER,
    height      INTEGER,
    format      TEXT    NOT NULL DEFAULT 'PNG',
    data_b64    TEXT    NOT NULL,   -- base64-encoded image bytes
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_stego_images_user_type ON stego_images (username, image_type);
CREATE INDEX IF NOT EXISTS idx_stego_images_created   ON stego_images (created_at);

-- ── encode_tasks ──────────────────────────────────────────────────────────────
-- One row per /api/encode call.
CREATE TABLE IF NOT EXISTS encode_tasks (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    task_token        TEXT    NOT NULL UNIQUE,  -- 32-char hex session token
    username          TEXT    NOT NULL,
    cover_image_id    INTEGER DEFAULT NULL REFERENCES stego_images(id) ON DELETE SET NULL,
    secret_image_id   INTEGER DEFAULT NULL REFERENCES stego_images(id) ON DELETE SET NULL,
    stego_image_id    INTEGER DEFAULT NULL REFERENCES stego_images(id) ON DELETE SET NULL,
    recovery_image_id INTEGER DEFAULT NULL REFERENCES stego_images(id) ON DELETE SET NULL,
    psnr_cover_stego  REAL    DEFAULT NULL,     -- dB
    ssim_cover_stego  REAL    DEFAULT NULL,     -- 0–1
    model_type        TEXT    NOT NULL DEFAULT 'HiNet',
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    expires_at        TEXT    NOT NULL           -- token TTL (default +10 min)
);

CREATE INDEX IF NOT EXISTS idx_encode_tasks_username ON encode_tasks (username);
CREATE INDEX IF NOT EXISTS idx_encode_tasks_created  ON encode_tasks (created_at);
CREATE INDEX IF NOT EXISTS idx_encode_tasks_expires  ON encode_tasks (expires_at);

-- ── decode_tasks ──────────────────────────────────────────────────────────────
-- One row per /api/decode call.
CREATE TABLE IF NOT EXISTS decode_tasks (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    username           TEXT    NOT NULL,
    stego_image_id     INTEGER DEFAULT NULL REFERENCES stego_images(id) ON DELETE SET NULL,
    recovered_image_id INTEGER DEFAULT NULL REFERENCES stego_images(id) ON DELETE SET NULL,
    decode_mode        TEXT    NOT NULL DEFAULT 'approximate',  -- exact | approximate | server
    created_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_decode_tasks_username ON decode_tasks (username);
CREATE INDEX IF NOT EXISTS idx_decode_tasks_created  ON decode_tasks (created_at);
