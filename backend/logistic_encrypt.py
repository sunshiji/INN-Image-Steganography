"""
Logistic Chaotic Map image encryption / decryption.

Encryption pipeline (per round):
  1. Pixel scrambling  — sort pixels by a chaotic index sequence
  2. Pixel diffusion   — XOR pixel values with a quantised chaotic sequence

Decryption is the exact inverse applied in reverse round order.

Usage
-----
from logistic_encrypt import encrypt_image, decrypt_image
from PIL import Image
import numpy as np

img  = np.array(Image.open("secret.png"))
enc, key = encrypt_image(img, r=3.9991, x0=0.37291, n0=500, rounds=2)
dec      = decrypt_image(enc, key)
"""

import numpy as np
from typing import Tuple, Dict, Any


# ---------------------------------------------------------------------------
# Logistic generator
# ---------------------------------------------------------------------------

def _logistic_sequence(r: float, x0: float, n0: int, length: int) -> np.ndarray:
    """Return *length* floats from the Logistic map after discarding n0 warm-up values."""
    x = float(x0)
    for _ in range(n0):
        x = r * x * (1.0 - x)
    seq = np.empty(length, dtype=np.float64)
    for i in range(length):
        x = r * x * (1.0 - x)
        seq[i] = x
    return seq


def _chaotic_permutation(seq: np.ndarray) -> np.ndarray:
    """Return an index array that sorts *seq* (used for pixel scrambling)."""
    return np.argsort(seq)


# ---------------------------------------------------------------------------
# Single-round helpers
# ---------------------------------------------------------------------------

def _scramble(flat: np.ndarray, perm: np.ndarray) -> np.ndarray:
    """Reorder *flat* pixels according to *perm*."""
    return flat[perm]


def _unscramble(flat: np.ndarray, perm: np.ndarray) -> np.ndarray:
    """Inverse of _scramble."""
    inv = np.empty_like(perm)
    inv[perm] = np.arange(len(perm))
    return flat[inv]


def _diffuse(flat: np.ndarray, key_seq: np.ndarray) -> np.ndarray:
    """XOR each pixel byte with a key byte derived from *key_seq*."""
    key_bytes = (key_seq * 255).astype(np.uint8)
    return (flat.astype(np.uint16) ^ key_bytes.astype(np.uint16)).astype(np.uint8)


# _undiffuse is identical to _diffuse (XOR is its own inverse)
_undiffuse = _diffuse


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def encrypt_image(
    image: np.ndarray,
    r: float = 3.9991,
    x0: float = 0.37291,
    n0: int = 500,
    rounds: int = 2,
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    Encrypt *image* (H×W×C uint8 numpy array) with the Logistic chaotic map.

    Returns
    -------
    encrypted : np.ndarray  — same shape/dtype as input
    key       : dict        — all parameters needed to decrypt
    """
    if image.ndim == 2:                  # grayscale → add channel dim
        image = image[:, :, np.newaxis]

    H, W, C = image.shape
    N = H * W                            # number of pixels per channel

    key: Dict[str, Any] = {"r": r, "x0": x0, "n0": n0, "rounds": rounds,
                            "H": H, "W": W, "C": C}

    result = image.copy()

    for round_idx in range(rounds):
        # Each round uses a freshly generated chaotic seed derived from x0
        # by advancing the map once per completed round (simple but sufficient)
        round_x0 = x0
        for _ in range(round_idx):
            round_x0 = r * round_x0 * (1.0 - round_x0)

        for c in range(C):
            flat = result[:, :, c].flatten()

            # --- scramble ---
            perm_seq = _logistic_sequence(r, round_x0, n0, N)
            perm = _chaotic_permutation(perm_seq)
            flat = _scramble(flat, perm)

            # --- diffuse ---
            diff_seq = _logistic_sequence(r, round_x0, n0 + N, N)
            flat = _diffuse(flat, diff_seq)

            result[:, :, c] = flat.reshape(H, W)

    return result, key


def decrypt_image(encrypted: np.ndarray, key: Dict[str, Any]) -> np.ndarray:
    """
    Decrypt an image produced by :func:`encrypt_image`.

    Parameters
    ----------
    encrypted : np.ndarray  — H×W×C uint8 array
    key       : dict        — the key dict returned by encrypt_image
    """
    r      = key["r"]
    x0     = key["x0"]
    n0     = key["n0"]
    rounds = key["rounds"]
    H, W, C = key["H"], key["W"], key["C"]

    if encrypted.ndim == 2:
        encrypted = encrypted[:, :, np.newaxis]

    N = H * W
    result = encrypted.copy()

    # Reverse round order
    for round_idx in reversed(range(rounds)):
        round_x0 = x0
        for _ in range(round_idx):
            round_x0 = r * round_x0 * (1.0 - round_x0)

        for c in range(C):
            flat = result[:, :, c].flatten()

            # --- un-diffuse ---
            diff_seq = _logistic_sequence(r, round_x0, n0 + N, N)
            flat = _undiffuse(flat, diff_seq)

            # --- un-scramble ---
            perm_seq = _logistic_sequence(r, round_x0, n0, N)
            perm = _chaotic_permutation(perm_seq)
            flat = _unscramble(flat, perm)

            result[:, :, c] = flat.reshape(H, W)

    return result


# ---------------------------------------------------------------------------
# Quality metrics helpers
# ---------------------------------------------------------------------------

def information_entropy(image: np.ndarray) -> float:
    """Shannon entropy of the image pixel values (ideal ≈ 8.0 for encrypted)."""
    flat = image.flatten().astype(np.uint8)
    counts = np.bincount(flat, minlength=256)
    probs = counts / counts.sum()
    probs = probs[probs > 0]
    return float(-np.sum(probs * np.log2(probs)))


def npcr(img1: np.ndarray, img2: np.ndarray) -> float:
    """Number of Pixels Change Rate (%) between two images."""
    return float(np.sum(img1 != img2) / img1.size * 100)


def uaci(img1: np.ndarray, img2: np.ndarray) -> float:
    """Unified Average Changing Intensity (%) between two images."""
    diff = np.abs(img1.astype(np.int32) - img2.astype(np.int32))
    return float(np.mean(diff) / 255 * 100)


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import os
    rng = np.random.default_rng(42)
    original = rng.integers(0, 256, (64, 64, 3), dtype=np.uint8)

    enc, key = encrypt_image(original, r=3.9991, x0=0.37291, n0=500, rounds=2)
    dec = decrypt_image(enc, key)

    assert np.array_equal(original, dec), "Decryption mismatch!"
    print("✓ Encrypt/decrypt round-trip OK")
    print(f"  Entropy (encrypted): {information_entropy(enc):.4f}  (original: {information_entropy(original):.4f})")
    print(f"  NPCR : {npcr(original, enc):.2f}%")
    print(f"  UACI : {uaci(original, enc):.2f}%")
