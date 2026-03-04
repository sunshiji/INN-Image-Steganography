"""
Flask REST API for the INN Image Steganography system.

Endpoints
---------
GET  /api/health
POST /api/encrypt          — Logistic chaotic map image encryption
POST /api/decrypt          — Logistic chaotic map decryption
POST /api/encode           — INN steganography: hide secret inside cover
POST /api/decode           — INN steganography: extract secret from stego
POST /api/pipeline/encrypt_encode  — encrypt secret then hide (one call)
POST /api/pipeline/decode_decrypt  — extract then decrypt (one call)

INN encode/decode key design
-----------------------------
encode returns:
  stego_image  : base64 PNG   — carrier image with hidden information
  stego_key    : base64 bytes — the INN "noise" tensor needed for exact decoding

decode accepts:
  stego        : file         — the stego PNG
  stego_key    : string (opt) — base64 noise from encode; if absent, approx mode
"""

import io
import base64
import os
import hmac

import numpy as np
from PIL import Image
from flask import Flask, request, jsonify, send_from_directory, session, redirect
from flask_cors import CORS
import torch

from logistic_encrypt import (
    encrypt_image,
    decrypt_image,
    information_entropy,
    npcr,
    uaci,
)
from inn_model import (
    INNSteganography,
    pil_to_tensor,
    tensor_to_pil,
    resize_to_match,
    ensure_even,
    psnr,
    ssim,
)

# ---------------------------------------------------------------------------
# App + model
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)

# Project root directory (one level up from backend/)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Startup sanity-check: warn if the main page is absent.
_index_path = os.path.join(ROOT_DIR, "index.html")
if not os.path.isfile(_index_path):
    print(
        f"[WARNING] index.html not found at {_index_path}. "
        "Static page serving will return 404 until the file is present.",
        flush=True,
    )

print("[INN] Loading model …", flush=True)
MODEL = INNSteganography.load(n_blocks=8)
print("[INN] Model ready.", flush=True)

MAX_DIM = 1024

# ---------------------------------------------------------------------------
# Authentication configuration
# Set SECRET_KEY, ADMIN_USERNAME, ADMIN_PASSWORD via environment variables.
# ---------------------------------------------------------------------------

app.secret_key = os.environ.get("SECRET_KEY", "inn-stego-dev-key-change-in-production")
if "SECRET_KEY" not in os.environ:
    print(
        "[WARNING] SECRET_KEY env var not set. Using insecure default key — "
        "set SECRET_KEY in production!",
        flush=True,
    )

ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "admin123")


@app.before_request
def _check_auth():
    """Redirect unauthenticated requests to /login; return 401 for API calls."""
    public = {"/login", "/api/auth/login"}
    if request.path in public:
        return None
    if not session.get("logged_in"):
        if request.path.startswith("/api/"):
            return jsonify({"error": "Unauthorized"}), 401
        return redirect("/login")


@app.route("/login")
def serve_login():
    if session.get("logged_in"):
        return redirect("/")
    return send_from_directory(ROOT_DIR, "login.html")


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    # Use compare_digest to prevent timing side-channel attacks
    ok = (
        hmac.compare_digest(username, ADMIN_USERNAME)
        and hmac.compare_digest(password, ADMIN_PASSWORD)
    )
    if ok:
        session["logged_in"] = True
        session["username"] = username
        return jsonify({"status": "ok"})
    return jsonify({"error": "用户名或密码错误"}), 401


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    session.clear()
    return jsonify({"status": "ok"})


@app.route("/api/auth/status", methods=["GET"])
def api_auth_status():
    if session.get("logged_in"):
        return jsonify({"logged_in": True, "username": session.get("username", "")})
    return jsonify({"logged_in": False}), 401

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_pil(fs) -> Image.Image:
    return Image.open(io.BytesIO(fs.read())).convert("RGB")


def _pil_to_b64(img: Image.Image, fmt: str = "PNG") -> str:
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _tensor_to_b64(t: torch.Tensor) -> str:
    """Serialise a float32 tensor to base64 for transport."""
    buf = io.BytesIO()
    np.save(buf, t.detach().numpy())
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _b64_to_tensor(s: str) -> torch.Tensor:
    data = base64.b64decode(s)
    arr  = np.load(io.BytesIO(data))
    return torch.from_numpy(arr)


def _resize_if_needed(img: Image.Image) -> Image.Image:
    w, h = img.size
    if max(w, h) > MAX_DIM:
        scale = MAX_DIM / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return ensure_even(img)


def _fp(name, default):
    try:    return float(request.form.get(name, default))
    except (ValueError, TypeError): return float(default)


def _ip(name, default):
    try:    return int(request.form.get(name, default))
    except (ValueError, TypeError): return int(default)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "model": "INN-Stego-v1"})


# ── Logistic Encrypt ────────────────────────────────────────────────────────

@app.route("/api/encrypt", methods=["POST"])
def api_encrypt():
    if "image" not in request.files:
        return jsonify({"error": "Missing 'image' field"}), 400
    try:
        img_pil = _load_pil(request.files["image"])
        img_pil = _resize_if_needed(img_pil)
        r, x0, n0, rounds = _fp("r",3.9991), _fp("x0",0.37291), _ip("n0",500), _ip("rounds",2)

        img_arr = np.array(img_pil)
        enc_arr, key = encrypt_image(img_arr, r=r, x0=x0, n0=n0, rounds=rounds)
        enc_pil = Image.fromarray(enc_arr.squeeze())

        metrics = {
            "entropy_original":  round(information_entropy(img_arr), 4),
            "entropy_encrypted": round(information_entropy(enc_arr), 4),
            "npcr": round(npcr(img_arr, enc_arr), 4),
            "uaci": round(uaci(img_arr, enc_arr), 4),
        }
        return jsonify({"encrypted_image": _pil_to_b64(enc_pil), "key": key, "metrics": metrics})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Logistic Decrypt ────────────────────────────────────────────────────────

@app.route("/api/decrypt", methods=["POST"])
def api_decrypt():
    if "image" not in request.files:
        return jsonify({"error": "Missing 'image' field"}), 400
    try:
        img_pil = _load_pil(request.files["image"])
        img_arr = np.array(img_pil)
        key = {
            "r": _fp("r",3.9991), "x0": _fp("x0",0.37291),
            "n0": _ip("n0",500),  "rounds": _ip("rounds",2),
            "H": _ip("H", img_arr.shape[0]),
            "W": _ip("W", img_arr.shape[1]),
            "C": _ip("C", img_arr.shape[2]),
        }
        dec_arr = decrypt_image(img_arr, key)
        dec_pil = Image.fromarray(dec_arr.squeeze())
        return jsonify({"decrypted_image": _pil_to_b64(dec_pil)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── INN Encode ──────────────────────────────────────────────────────────────

@app.route("/api/encode", methods=["POST"])
def api_encode():
    if "cover" not in request.files or "secret" not in request.files:
        return jsonify({"error": "Both 'cover' and 'secret' fields required"}), 400
    try:
        cover_pil  = _resize_if_needed(_load_pil(request.files["cover"]))
        secret_pil = ensure_even(resize_to_match(cover_pil, _load_pil(request.files["secret"])))

        ct = pil_to_tensor(cover_pil)
        st = pil_to_tensor(secret_pil)

        with torch.no_grad():
            stego_t, noise_t = MODEL.encode(ct, st)

        stego_pil  = tensor_to_pil(stego_t)
        cover_arr  = np.array(cover_pil)
        stego_arr  = np.array(stego_pil)

        metrics = {
            "psnr_cover_stego": round(psnr(cover_arr, stego_arr), 2),
            "ssim_cover_stego": round(ssim(cover_arr, stego_arr), 4),
        }
        return jsonify({
            "stego_image": _pil_to_b64(stego_pil),
            "stego_key":   _tensor_to_b64(noise_t),   # keep for exact decode
            "metrics":     metrics,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── INN Decode ──────────────────────────────────────────────────────────────

@app.route("/api/decode", methods=["POST"])
def api_decode():
    if "stego" not in request.files:
        return jsonify({"error": "Missing 'stego' field"}), 400
    try:
        stego_pil = ensure_even(_load_pil(request.files["stego"]))
        st = pil_to_tensor(stego_pil)

        # stego_key is optional — if provided, recovery is exact
        noise_t = None
        key_b64 = request.form.get("stego_key", "")
        if key_b64:
            noise_t = _b64_to_tensor(key_b64)

        with torch.no_grad():
            secret_t = MODEL.decode(st, noise_t)

        secret_pil = tensor_to_pil(secret_t)
        mode = "exact" if noise_t is not None else "approximate"
        return jsonify({
            "secret_image": _pil_to_b64(secret_pil),
            "mode": mode,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Pipeline: encrypt → encode ──────────────────────────────────────────────

@app.route("/api/pipeline/encrypt_encode", methods=["POST"])
def api_pipeline_encrypt_encode():
    if "cover" not in request.files or "secret" not in request.files:
        return jsonify({"error": "Both 'cover' and 'secret' fields required"}), 400
    try:
        cover_pil  = _resize_if_needed(_load_pil(request.files["cover"]))
        secret_pil = ensure_even(resize_to_match(cover_pil, _load_pil(request.files["secret"])))
        r, x0, n0, rounds = _fp("r",3.9991), _fp("x0",0.37291), _ip("n0",500), _ip("rounds",2)

        # Step 1: Logistic encrypt secret
        sec_arr = np.array(secret_pil)
        enc_arr, chaos_key = encrypt_image(sec_arr, r=r, x0=x0, n0=n0, rounds=rounds)
        enc_pil = Image.fromarray(enc_arr.squeeze())

        encrypt_metrics = {
            "entropy_original":  round(information_entropy(sec_arr), 4),
            "entropy_encrypted": round(information_entropy(enc_arr), 4),
            "npcr": round(npcr(sec_arr, enc_arr), 4),
            "uaci": round(uaci(sec_arr, enc_arr), 4),
        }

        # Step 2: INN encode
        ct = pil_to_tensor(cover_pil)
        et = pil_to_tensor(enc_pil)

        with torch.no_grad():
            stego_t, noise_t = MODEL.encode(ct, et)

        stego_pil = tensor_to_pil(stego_t)
        cover_arr = np.array(cover_pil)
        stego_arr = np.array(stego_pil)

        inn_metrics = {
            "psnr_cover_stego": round(psnr(cover_arr, stego_arr), 2),
            "ssim_cover_stego": round(ssim(cover_arr, stego_arr), 4),
        }

        return jsonify({
            "encrypted_secret": _pil_to_b64(enc_pil),
            "stego_image":      _pil_to_b64(stego_pil),
            "chaos_key":        chaos_key,
            "stego_key":        _tensor_to_b64(noise_t),
            "encrypt_metrics":  encrypt_metrics,
            "inn_metrics":      inn_metrics,
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── Pipeline: decode → decrypt ──────────────────────────────────────────────

@app.route("/api/pipeline/decode_decrypt", methods=["POST"])
def api_pipeline_decode_decrypt():
    if "stego" not in request.files:
        return jsonify({"error": "Missing 'stego' field"}), 400
    try:
        stego_pil = ensure_even(_load_pil(request.files["stego"]))
        st = pil_to_tensor(stego_pil)

        noise_t = None
        key_b64 = request.form.get("stego_key", "")
        if key_b64:
            noise_t = _b64_to_tensor(key_b64)

        with torch.no_grad():
            secret_enc_t = MODEL.decode(st, noise_t)

        secret_enc_pil = tensor_to_pil(secret_enc_t)
        enc_arr = np.array(secret_enc_pil)

        r, x0, n0, rounds = _fp("r",3.9991), _fp("x0",0.37291), _ip("n0",500), _ip("rounds",2)
        chaos_key = {
            "r": r, "x0": x0, "n0": n0, "rounds": rounds,
            "H": enc_arr.shape[0], "W": enc_arr.shape[1], "C": enc_arr.shape[2],
        }
        dec_arr = decrypt_image(enc_arr, chaos_key)
        dec_pil = Image.fromarray(dec_arr.squeeze())

        return jsonify({
            "extracted_encrypted": _pil_to_b64(secret_enc_pil),
            "decrypted_secret":    _pil_to_b64(dec_pil),
            "mode": "exact" if noise_t is not None else "approximate",
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------------------------------------------------------------------
# Static file serving — serves HTML pages and assets from the project root.
# Flask's registered API routes take priority over this catch-all.
#
# Security: reject requests for hidden paths (e.g. .git/) and the
# backend/ source directory so Python source code is not exposed.
# ---------------------------------------------------------------------------

def _is_safe_static_path(filename: str) -> bool:
    """Return True only if *filename* is safe to serve as a static asset."""
    # Normalise separators and strip leading slashes
    parts = filename.replace("\\", "/").lstrip("/").split("/")
    # Block hidden files / directories (names starting with '.')
    if any(part.startswith(".") for part in parts):
        return False
    # Block the backend source directory
    if parts[0].lower() == "backend":
        return False
    return True


@app.route("/")
def serve_root():
    return send_from_directory(ROOT_DIR, "index.html")


@app.route("/<path:filename>")
def serve_static(filename):
    if not _is_safe_static_path(filename):
        return jsonify({"error": "Not found"}), 404
    return send_from_directory(ROOT_DIR, filename)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
