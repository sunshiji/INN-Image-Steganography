-- =============================================================================
-- INN Image Steganography System — MySQL 8 database schema
--
-- Usage:
--   mysql -u root -p < backend/schema.sql
--
-- Environment variables expected by backend/db.py:
--   MYSQL_HOST      (default: localhost)
--   MYSQL_PORT      (default: 3306)
--   MYSQL_USER      (default: inn_stego)
--   MYSQL_PASSWORD  (required)
--   MYSQL_DB        (default: inn_stego_db)
-- =============================================================================

SET NAMES utf8mb4;
SET time_zone = '+00:00';

CREATE DATABASE IF NOT EXISTS inn_stego_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE inn_stego_db;

-- ── users ─────────────────────────────────────────────────────────────────────
-- Mirrors the JSON file store (backend/.inn-stego-users.json).
-- The file store continues to work as a fallback when MySQL is unavailable.

CREATE TABLE IF NOT EXISTS users (
  id            INT UNSIGNED        NOT NULL AUTO_INCREMENT,
  username      VARCHAR(50)         NOT NULL,
  password_hash VARCHAR(255)        NOT NULL COMMENT 'pbkdf2_hmac SHA-256: salt$hex',
  role          ENUM('admin','user') NOT NULL DEFAULT 'user',
  created_at    DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at    DATETIME            NOT NULL DEFAULT CURRENT_TIMESTAMP
                                             ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uq_username (username)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── stego_images ──────────────────────────────────────────────────────────────
-- Stores every image produced or consumed by the system:
--   cover      — original carrier image uploaded by user
--   secret     — original secret image (before encryption)
--   encrypted  — chaos-encrypted secret image
--   stego      — INN-encoded stego image (cover + hidden secret)
--   recovery   — exact decoded secret (recovered at encode time, server-side)
--
-- data_b64 holds the raw PNG/JPEG as a base64 string (MEDIUMTEXT: up to 16 MB).
-- For very large images (>12 MB base64) use LONGTEXT instead.

CREATE TABLE IF NOT EXISTS stego_images (
  id            INT UNSIGNED   NOT NULL AUTO_INCREMENT,
  username      VARCHAR(50)    NOT NULL  COMMENT 'owner / uploader username',
  image_type    ENUM('cover','secret','encrypted','stego','recovery')
                               NOT NULL,
  filename      VARCHAR(255)   NOT NULL  DEFAULT 'image.png',
  width         SMALLINT UNSIGNED,
  height        SMALLINT UNSIGNED,
  format        VARCHAR(10)    NOT NULL  DEFAULT 'PNG',
  data_b64      MEDIUMTEXT     NOT NULL  COMMENT 'base64-encoded image bytes (PNG)',
  created_at    DATETIME       NOT NULL  DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_user_type    (username, image_type),
  INDEX idx_created      (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── encode_tasks ──────────────────────────────────────────────────────────────
-- One row per /api/encode call.  Links to the four images involved and stores
-- quality metrics (PSNR, SSIM).  task_token corresponds to the server-side
-- session token returned to the browser so the decode page can retrieve the
-- pre-computed recovery image without re-running inference.

CREATE TABLE IF NOT EXISTS encode_tasks (
  id                INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  task_token        CHAR(32)        NOT NULL  COMMENT '32-char hex session token',
  username          VARCHAR(50)     NOT NULL,
  cover_image_id    INT UNSIGNED             DEFAULT NULL,
  secret_image_id   INT UNSIGNED             DEFAULT NULL,
  stego_image_id    INT UNSIGNED             DEFAULT NULL,
  recovery_image_id INT UNSIGNED             DEFAULT NULL,
  psnr_cover_stego  FLOAT                    DEFAULT NULL  COMMENT 'dB',
  ssim_cover_stego  FLOAT                    DEFAULT NULL  COMMENT '0–1',
  model_type        ENUM('INN','HiNet')      NOT NULL DEFAULT 'HiNet',
  created_at        DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  expires_at        DATETIME        NOT NULL COMMENT 'token TTL (default +10 min)',
  PRIMARY KEY (id),
  UNIQUE KEY uq_task_token     (task_token),
  INDEX idx_username           (username),
  INDEX idx_created            (created_at),
  INDEX idx_expires            (expires_at),
  CONSTRAINT fk_enc_cover
    FOREIGN KEY (cover_image_id)    REFERENCES stego_images(id) ON DELETE SET NULL,
  CONSTRAINT fk_enc_secret
    FOREIGN KEY (secret_image_id)   REFERENCES stego_images(id) ON DELETE SET NULL,
  CONSTRAINT fk_enc_stego
    FOREIGN KEY (stego_image_id)    REFERENCES stego_images(id) ON DELETE SET NULL,
  CONSTRAINT fk_enc_recovery
    FOREIGN KEY (recovery_image_id) REFERENCES stego_images(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── decode_tasks ──────────────────────────────────────────────────────────────
-- One row per /api/decode call.

CREATE TABLE IF NOT EXISTS decode_tasks (
  id                 INT UNSIGNED    NOT NULL AUTO_INCREMENT,
  username           VARCHAR(50)     NOT NULL,
  stego_image_id     INT UNSIGNED             DEFAULT NULL,
  recovered_image_id INT UNSIGNED             DEFAULT NULL,
  decode_mode        ENUM('exact','approximate','server')
                                     NOT NULL DEFAULT 'approximate',
  created_at         DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  INDEX idx_username  (username),
  INDEX idx_created   (created_at),
  CONSTRAINT fk_dec_stego
    FOREIGN KEY (stego_image_id)     REFERENCES stego_images(id) ON DELETE SET NULL,
  CONSTRAINT fk_dec_recovered
    FOREIGN KEY (recovered_image_id) REFERENCES stego_images(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ── Stored procedure: purge expired tokens and orphaned images ────────────────

DROP PROCEDURE IF EXISTS purge_expired_tasks;

DELIMITER $$
CREATE PROCEDURE purge_expired_tasks()
BEGIN
  -- Remove encode tasks whose session token has expired
  DELETE FROM encode_tasks WHERE expires_at < NOW();

  -- Remove images that are no longer referenced by any task
  DELETE FROM stego_images
  WHERE id NOT IN (
    SELECT cover_image_id    FROM encode_tasks WHERE cover_image_id    IS NOT NULL
    UNION ALL
    SELECT secret_image_id   FROM encode_tasks WHERE secret_image_id   IS NOT NULL
    UNION ALL
    SELECT stego_image_id    FROM encode_tasks WHERE stego_image_id    IS NOT NULL
    UNION ALL
    SELECT recovery_image_id FROM encode_tasks WHERE recovery_image_id IS NOT NULL
    UNION ALL
    SELECT stego_image_id    FROM decode_tasks WHERE stego_image_id    IS NOT NULL
    UNION ALL
    SELECT recovered_image_id FROM decode_tasks WHERE recovered_image_id IS NOT NULL
  );
END$$
DELIMITER ;


-- ── Event scheduler: auto-purge every hour ────────────────────────────────────
-- Requires the MySQL Event Scheduler to be enabled:
--   SET GLOBAL event_scheduler = ON;
-- Or add  event_scheduler=ON  to /etc/mysql/my.cnf

DROP EVENT IF EXISTS evt_purge_expired;

CREATE EVENT evt_purge_expired
  ON SCHEDULE EVERY 1 HOUR
  STARTS (TIMESTAMP(CURRENT_DATE) + INTERVAL HOUR(NOW()) + 1 HOUR)
  DO CALL purge_expired_tasks();
