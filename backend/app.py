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
import json
import os
import hmac
import hashlib
import secrets
import time as _time
import threading as _threading

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
from hinet_model import HiNetSteganography

# ---------------------------------------------------------------------------
# App + model
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)

# Project root directory (one level up from backend/)
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

# Fixed pre-trained HiNet weights path (production server).
# Override via env var HINET_WEIGHTS_FIXED_PATH for non-default deployments.
# This is checked first; the user-uploaded path is a secondary fallback.
HINET_WEIGHTS_FIXED_PATH = os.environ.get(
    "HINET_WEIGHTS_FIXED_PATH",
    "/home/sunshiji/system/Hinet_sys/INN-Image-Steganography/weight/model_best_s.pt",
)

# Directory for user-uploaded model weights (secondary)
WEIGHTS_DIR = os.path.join(os.path.expanduser("~"), ".inn-stego-weights")
HINET_WEIGHTS_FILE = os.path.join(WEIGHTS_DIR, "hinet_weights.pt")

# ---------------------------------------------------------------------------
# In-memory cross-page session store (avoids sessionStorage 5 MB quota limit)
# Maps token (UUID hex) → {'stego_image': b64, 'stego_key': str, 'ts': float}
# ---------------------------------------------------------------------------

_SESSION_STORE: dict = {}
_SESSION_LOCK = _threading.Lock()
_SESSION_TTL = 600  # 10 minutes


def _session_cleanup() -> None:
    """Remove expired entries from the in-memory session store."""
    now = _time.time()
    with _SESSION_LOCK:
        expired = [k for k, v in _SESSION_STORE.items() if now - v["ts"] > _SESSION_TTL]
        for k in expired:
            del _SESSION_STORE[k]


# Startup sanity-check: warn if the main page is absent.
_index_path = os.path.join(ROOT_DIR, "index.html")
if not os.path.isfile(_index_path):
    print(
        f"[WARNING] index.html not found at {_index_path}. "
        "Static page serving will return 404 until the file is present.",
        flush=True,
    )

print("[INN] model import OK — will load on first request.", flush=True)
_MODEL = None
_HINET_MODEL = None


def _get_model():
    """Lazily initialise the steganography model inside the worker process.

    Priority order for HiNet weights:
      1. Fixed production path (HINET_WEIGHTS_FIXED_PATH)
      2. User-uploaded path (HINET_WEIGHTS_FILE)
      3. Fall back to built-in INNSteganography (random-init, near-identity)

    Deferring model creation until after Gunicorn forks avoids the well-known
    PyTorch/OpenMP fork deadlock that silently prevents sync workers from
    responding.  The post_fork hook in gunicorn.conf.py already caps the
    OpenMP/MKL thread pool to 1 before this code runs; the guard below is a
    belt-and-suspenders fallback for non-gunicorn entry points (e.g.
    ``flask run`` or ``python app.py``).
    """
    global _MODEL, _HINET_MODEL
    try:
        os.environ.setdefault("OMP_NUM_THREADS", "1")
        os.environ.setdefault("MKL_NUM_THREADS", "1")
        torch.set_num_threads(1)
    except Exception:
        pass

    # Prefer HiNet when pre-trained weights are available.
    # Check the fixed production path first, then the user-uploaded path.
    hinet_weights_path = None
    if os.path.isfile(HINET_WEIGHTS_FIXED_PATH):
        hinet_weights_path = HINET_WEIGHTS_FIXED_PATH
    elif os.path.isfile(HINET_WEIGHTS_FILE):
        hinet_weights_path = HINET_WEIGHTS_FILE

    if hinet_weights_path:
        if _HINET_MODEL is None:
            print(f"[HiNet] Loading model from {hinet_weights_path} …", flush=True)
            _HINET_MODEL = HiNetSteganography.load(weights_path=hinet_weights_path)
            print("[HiNet] Model ready.", flush=True)
        return _HINET_MODEL

    # Fall back to built-in INN
    if _MODEL is None:
        print("[INN] Loading model …", flush=True)
        _MODEL = INNSteganography.load(n_blocks=8)
        print("[INN] Model ready.", flush=True)
    return _MODEL

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

# ---------------------------------------------------------------------------
# Multi-user store  (stored in ~/.inn-stego-users.json)
# Env-var admin is always the ultimate fallback; file users take precedence
# when a matching entry exists.
# ---------------------------------------------------------------------------

USERS_FILE = os.path.join(os.path.expanduser("~"), ".inn-stego-users.json")
_MIN_PASSWORD_LEN = 6


def _hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
    return f"{salt}${h.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt, h = stored.split("$", 1)
        h2 = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000)
        return hmac.compare_digest(h, h2.hex())
    except Exception:
        return False


def _load_users() -> dict:
    if os.path.isfile(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and "users" in data:
                return data
        except Exception:
            pass
    return {"users": {}}


def _save_users(data: dict) -> None:
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    try:
        os.chmod(USERS_FILE, 0o600)
    except OSError:
        pass


def _auth_user(username: str, password: str) -> bool:
    """Verify credentials: check file store first, then env-var admin fallback."""
    store = _load_users()
    entry = store.get("users", {}).get(username)
    if entry:
        return _verify_password(password, entry.get("password_hash", ""))
    # Fallback: env-var admin
    return (
        hmac.compare_digest(username, ADMIN_USERNAME)
        and hmac.compare_digest(password, ADMIN_PASSWORD)
    )


@app.before_request
def _check_auth():
    """Redirect unauthenticated requests to /login; return 401 for API calls."""
    public = {
        "/login", "/api/auth/login",
        "/register", "/api/auth/register",
        "/forgot-password", "/api/auth/reset-password",
        "/api/health",
    }
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


@app.route("/register")
def serve_register():
    if session.get("logged_in"):
        return redirect("/")
    return send_from_directory(ROOT_DIR, "register.html")


@app.route("/forgot-password")
def serve_forgot_password():
    return send_from_directory(ROOT_DIR, "forgot-password.html")


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if _auth_user(username, password):
        session["logged_in"] = True
        session["username"] = username
        return jsonify({"status": "ok"})
    return jsonify({"error": "用户名或密码错误"}), 401


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    session.clear()
    return jsonify({"status": "ok"})


@app.route("/api/auth/register", methods=["POST"])
def api_auth_register():
    """Create a new user. Requires invite_code == SECRET_KEY."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    invite_code = data.get("invite_code") or ""

    if not all([username, password, invite_code]):
        return jsonify({"error": "缺少必填字段"}), 400
    if not hmac.compare_digest(invite_code, str(app.secret_key)):
        return jsonify({"error": "邀请码错误"}), 401
    if len(password) < _MIN_PASSWORD_LEN:
        return jsonify({"error": f"密码至少需要 {_MIN_PASSWORD_LEN} 位字符"}), 400
    if len(username) < 2 or len(username) > 32:
        return jsonify({"error": "用户名长度应为 2–32 位字符"}), 400

    store = _load_users()
    users = store.setdefault("users", {})

    # Prevent creating a file entry that shadows the env-var admin
    if username == ADMIN_USERNAME or username in users:
        return jsonify({"error": "用户名已存在"}), 409

    users[username] = {"password_hash": _hash_password(password), "role": "user"}
    _save_users(store)
    return jsonify({"status": "ok", "message": "注册成功，请返回登录页面"})


@app.route("/api/auth/reset-password", methods=["POST"])
def api_auth_reset_password():
    """Reset a user's password. Requires recovery_code == SECRET_KEY."""
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    recovery_code = data.get("recovery_code") or ""
    new_password = data.get("new_password") or ""

    if not all([username, recovery_code, new_password]):
        return jsonify({"error": "缺少必填字段"}), 400
    if not hmac.compare_digest(recovery_code, str(app.secret_key)):
        return jsonify({"error": "恢复码错误"}), 401
    if len(new_password) < _MIN_PASSWORD_LEN:
        return jsonify({"error": f"新密码至少需要 {_MIN_PASSWORD_LEN} 位字符"}), 400

    store = _load_users()
    users = store.setdefault("users", {})

    # Allow resetting env-var admin: create/update their file entry
    # After reset, the file entry takes precedence over the env var
    users[username] = {
        **users.get(username, {"role": "admin" if username == ADMIN_USERNAME else "user"}),
        "password_hash": _hash_password(new_password),
    }
    _save_users(store)
    return jsonify({"status": "ok", "message": "密码已重置，请返回登录页面"})


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
            stego_t, noise_t = _get_model().encode(ct, st)

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
            secret_t = _get_model().decode(st, noise_t)

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
            stego_t, noise_t = _get_model().encode(ct, et)

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
            secret_enc_t = _get_model().decode(st, noise_t)

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


# ── Model management ────────────────────────────────────────────────────────

@app.route("/api/model/status", methods=["GET"])
def api_model_status():
    """Return which steganography model is currently active."""
    fixed_loaded  = os.path.isfile(HINET_WEIGHTS_FIXED_PATH)
    upload_loaded = os.path.isfile(HINET_WEIGHTS_FILE)
    hinet_loaded  = fixed_loaded or upload_loaded

    if fixed_loaded:
        active_path = HINET_WEIGHTS_FIXED_PATH
    elif upload_loaded:
        active_path = HINET_WEIGHTS_FILE
    else:
        active_path = None

    return jsonify({
        "active_model": "HiNet" if hinet_loaded else "INN",
        "hinet_weights_loaded": hinet_loaded,
        "hinet_weights_path": active_path,
    })


@app.route("/api/model/upload_weights", methods=["POST"])
def api_model_upload_weights():
    """Upload a pre-trained HiNet checkpoint (.pt file).

    The file is saved to HINET_WEIGHTS_FILE and the HiNet model is
    re-initialised on the next encode/decode call.

    Expected form field: ``weights`` (file)
    Optional form field: ``action=remove`` to delete existing weights and
                         revert to the built-in INN model.
    """
    global _HINET_MODEL

    # Allow removing weights to revert to built-in INN
    if request.form.get("action") == "remove":
        if os.path.isfile(HINET_WEIGHTS_FILE):
            os.remove(HINET_WEIGHTS_FILE)
        _HINET_MODEL = None
        return jsonify({"status": "ok", "message": "已移除 HiNet 权重，已切换回内置 INN 模型"})

    if "weights" not in request.files:
        return jsonify({"error": "缺少 'weights' 文件字段"}), 400

    f = request.files["weights"]
    if not f.filename:
        return jsonify({"error": "未选择文件"}), 400
    if not f.filename.lower().endswith(".pt"):
        return jsonify({"error": "权重文件必须是 .pt 格式"}), 400

    try:
        raw = f.read()
        # Validate the file is a valid PyTorch checkpoint
        ckpt = torch.load(io.BytesIO(raw), map_location="cpu")
        if isinstance(ckpt, dict):
            state_dict = ckpt.get("net", ckpt)
        else:
            return jsonify({"error": "不支持的 checkpoint 格式（需要包含 'net' key 的字典，或直接的 state_dict）"}), 400

        # Quick architecture check: verify at least one expected key exists
        keys = list(state_dict.keys())
        stripped = [k[len("module."):] if k.startswith("module.") else k for k in keys]
        has_inv = any("inv1" in k or "inv_blocks" in k for k in stripped)
        if not has_inv:
            return jsonify({"error": "权重文件与 HiNet 架构不匹配（未找到 inv1 层）"}), 400

        # Save to disk
        os.makedirs(WEIGHTS_DIR, exist_ok=True)
        with open(HINET_WEIGHTS_FILE, "wb") as out:
            out.write(raw)

        # Force re-load on next request
        _HINET_MODEL = None

        return jsonify({
            "status": "ok",
            "message": "HiNet 权重已成功上传，下次推理时将自动使用 HiNet 模型",
            "keys_count": len(keys),
        })
    except Exception as e:
        return jsonify({"error": f"权重文件无效: {e}"}), 400


# ── Cross-page session store (solves sessionStorage 5 MB quota limit) ─────

@app.route("/api/session/store", methods=["POST"])
def api_session_store():
    """Store stego image + key server-side, return a short-lived token.

    Request body (JSON):
        stego_image : base64 string
        stego_key   : base64 string (optional)

    Response:
        { "token": "<uuid_hex>" }
    """
    _session_cleanup()
    data = request.get_json(silent=True) or {}
    stego_image = data.get("stego_image", "")
    stego_key   = data.get("stego_key",   "")
    if not stego_image:
        return jsonify({"error": "缺少 stego_image 字段"}), 400
    token = secrets.token_hex(16)
    with _SESSION_LOCK:
        _SESSION_STORE[token] = {
            "stego_image": stego_image,
            "stego_key":   stego_key,
            "ts":          _time.time(),
        }
    return jsonify({"token": token})


@app.route("/api/session/load/<token>", methods=["GET"])
def api_session_load(token: str):
    """Retrieve and delete a stored session by token.

    Response:
        { "stego_image": "...", "stego_key": "..." }
    """
    # Validate token format: must be exactly 32 lowercase hex characters
    if not token or len(token) != 32 or not all(c in "0123456789abcdef" for c in token):
        return jsonify({"error": "会话令牌格式无效"}), 400
    _session_cleanup()
    with _SESSION_LOCK:
        entry = _SESSION_STORE.pop(token, None)
    if entry is None:
        return jsonify({"error": "会话令牌无效或已过期"}), 404
    return jsonify({
        "stego_image": entry["stego_image"],
        "stego_key":   entry["stego_key"],
    })


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
