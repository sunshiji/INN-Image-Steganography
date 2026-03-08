"""
HiNet steganography backend — self-contained PyTorch wrapper.

Architecture is a faithful replica of the HiNetcp/ code that ships with this
repo so that checkpoints saved by HiNetcp/train.py can be loaded without any
key remapping.

Key design decisions
--------------------
* DWT / IWT are implemented inline (no dependency on HiNetcp/).
* The attribute names inside _Model / _Hinet / INV_block intentionally mirror
  the originals so torch.load works without remapping:
      DataParallel checkpoint key  :  module.model.inv1.r.conv1.weight
      After stripping "module."    :  model.inv1.r.conv1.weight
      State-dict key in this file  :  _backbone.model.inv1.r.conv1.weight
  → load_weights() prefixes all keys with "_backbone." before loading.
* encode() / decode() follow the same API as INNSteganography in inn_model.py.
"""

import io
import os

import numpy as np
import torch
import torch.nn as nn
from PIL import Image

# ---------------------------------------------------------------------------
# Constants (mirrors HiNetcp/config.py)
# ---------------------------------------------------------------------------
_CLAMP = 2.0
_C = 3          # RGB channels per image
_SPLIT = _C * 4  # wavelet-domain channels per stream (12)


# ---------------------------------------------------------------------------
# Haar Wavelet DWT / IWT  (device-agnostic; matching dwt_init / iwt_init
# from HiNetcp/modules/Unet_common.py but without the global `device` ref)
# ---------------------------------------------------------------------------

def _dwt(x: torch.Tensor) -> torch.Tensor:
    """2-D Haar DWT: (B, C, H, W) → (B, 4C, H/2, W/2)"""
    x01 = x[:, :, 0::2, :] / 2
    x02 = x[:, :, 1::2, :] / 2
    x1 = x01[:, :, :, 0::2]
    x2 = x02[:, :, :, 0::2]
    x3 = x01[:, :, :, 1::2]
    x4 = x02[:, :, :, 1::2]
    return torch.cat((x1 + x2 + x3 + x4,
                      -x1 - x2 + x3 + x4,
                      -x1 + x2 - x3 + x4,
                       x1 - x2 - x3 + x4), dim=1)


def _iwt(x: torch.Tensor) -> torch.Tensor:
    """Inverse 2-D Haar DWT: (B, 4C, H/2, W/2) → (B, C, H, W)"""
    _, C4, H2, W2 = x.shape
    C = C4 // 4
    x1 = x[:, :C,    :, :] / 2
    x2 = x[:, C:2*C, :, :] / 2
    x3 = x[:, 2*C:3*C, :, :] / 2
    x4 = x[:, 3*C:,  :, :] / 2
    h = torch.zeros(x.shape[0], C, H2 * 2, W2 * 2,
                    dtype=x.dtype, device=x.device)
    h[:, :, 0::2, 0::2] = x1 - x2 - x3 + x4
    h[:, :, 1::2, 0::2] = x1 - x2 + x3 - x4
    h[:, :, 0::2, 1::2] = x1 + x2 - x3 - x4
    h[:, :, 1::2, 1::2] = x1 + x2 + x3 + x4
    return h


class _DWT(nn.Module):
    def __init__(self):
        super().__init__()
        self.requires_grad = False

    def forward(self, x):
        return _dwt(x)


class _IWT(nn.Module):
    def __init__(self):
        super().__init__()
        self.requires_grad = False

    def forward(self, x):
        return _iwt(x)


# ---------------------------------------------------------------------------
# Spatial Attention Block  (mirrors add/res_ab.py  +  SAB from the same file)
# ---------------------------------------------------------------------------

class _ChannelPool(nn.Module):
    """ChannelPool: concatenate max-pool and mean-pool across channels."""
    def forward(self, x):
        return torch.cat((torch.max(x, 1)[0].unsqueeze(1),
                          torch.mean(x, 1).unsqueeze(1)), dim=1)


class _Basic(nn.Module):
    """The tiny 'Basic' head used inside SAB (mirrors Basic in res_ab.py)."""
    def __init__(self, in_planes, out_planes, kernel_size, padding=0, bias=False):
        super().__init__()
        self.out_channels = out_planes
        self.conv = nn.Conv2d(in_planes, out_planes, kernel_size=kernel_size,
                              padding=padding, bias=bias)
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.conv(x))


class _SAB(nn.Module):
    """Spatial Attention Block (mirrors SAB in res_ab.py)."""
    def __init__(self):
        super().__init__()
        self.compress = _ChannelPool()
        self.spatial = _Basic(2, 1, kernel_size=3, padding=1, bias=False)

    def forward(self, x):
        return x * torch.sigmoid(self.spatial(self.compress(x)))


class Residual_Attention_Block(nn.Module):
    """Mirrors Residual_Attention_Block in HiNetcp/add/res_ab.py."""
    def __init__(self, in_channels=6, out_channels=6, bias=True):
        super().__init__()
        k, s, p = 3, 1, 1
        self.res = nn.Sequential(
            nn.Conv2d(in_channels, out_channels, k, s, p, bias=bias),
            nn.ReLU(inplace=False),
            nn.Conv2d(in_channels, out_channels, k, s, p, bias=bias),
        )
        self.sab = _SAB()

    def forward(self, x):
        x1 = x + self.res(x)
        x2 = x1 + self.res(x1)
        x3 = x2 + self.res(x2)
        x3_1 = x1 + x3
        x4 = x3_1 + self.res(x3_1)
        x4_1 = x + x4
        return x + self.sab(x4_1)


# ---------------------------------------------------------------------------
# ResidualDenseBlock_out  (mirrors HiNetcp/rrdb_denselayer.py)
# ---------------------------------------------------------------------------

class ResidualDenseBlock_out(nn.Module):
    """6-conv dense block with a Residual_Attention_Block skip.

    Architecture matches HiNetcp/rrdb_denselayer.py (the active, non-commented
    version with conv1…conv6 and an attention residual).
    """
    def __init__(self, input: int, output: int, bias: bool = True):
        super().__init__()
        self.conv1 = nn.Conv2d(input,          32,     3, 1, 1, bias=bias)
        self.conv2 = nn.Conv2d(input + 32,     32,     3, 1, 1, bias=bias)
        self.conv3 = nn.Conv2d(input + 64,     32,     3, 1, 1, bias=bias)
        self.conv4 = nn.Conv2d(input + 96,     32,     3, 1, 1, bias=bias)
        self.conv5 = nn.Conv2d(input + 128,    32,     3, 1, 1, bias=bias)
        self.conv6 = nn.Conv2d(input + 160,    output, 3, 1, 1, bias=bias)
        self.res   = Residual_Attention_Block(input, output, bias=bias)
        self.lrelu = nn.LeakyReLU(inplace=False)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.lrelu(self.conv5(torch.cat((x, x1, x2, x3, x4), 1)))
        x6 = self.conv6(torch.cat((x, x1, x2, x3, x4, x5), 1))
        return self.res(x6)


# ---------------------------------------------------------------------------
# INV_block  (mirrors HiNetcp/invblock.py)
# ---------------------------------------------------------------------------

class INV_block(nn.Module):
    """Affine coupling block with ρ, η, φ sub-nets (mirrors invblock.py)."""
    def __init__(self,
                 subnet_constructor=ResidualDenseBlock_out,
                 clamp: float = _CLAMP,
                 in_1: int = _C,
                 in_2: int = _C):
        super().__init__()
        split1 = in_1 * 4
        split2 = in_2 * 4
        self.split_len1 = split1
        self.split_len2 = split2
        self.clamp = clamp
        self.r = subnet_constructor(split1, split2)
        self.y = subnet_constructor(split1, split2)
        self.f = subnet_constructor(split2, split1)

    def _e(self, s):
        return torch.exp(self.clamp * 2 * (torch.sigmoid(s) - 0.5))

    def forward(self, x, rev: bool = False):
        x1 = x.narrow(1, 0, self.split_len1)
        x2 = x.narrow(1, self.split_len1, self.split_len2)
        if not rev:
            t2 = self.f(x2)
            y1 = x1 + t2
            s1, t1 = self.r(y1), self.y(y1)
            y2 = self._e(s1) * x2 + t1
        else:
            s1, t1 = self.r(x1), self.y(x1)
            y2 = (x2 - t1) / self._e(s1)
            t2 = self.f(y2)
            y1 = x1 - t2
        return torch.cat((y1, y2), 1)


# ---------------------------------------------------------------------------
# Hinet  (mirrors HiNetcp/hinet.py — uses individual attrs inv1…inv16
#          so that state-dict keys from train.py load without remapping)
# ---------------------------------------------------------------------------

class _Hinet(nn.Module):
    """16-block invertible network (mirrors HiNetcp/hinet.py Hinet class)."""
    def __init__(self):
        super().__init__()
        self.inv1  = INV_block()
        self.inv2  = INV_block()
        self.inv3  = INV_block()
        self.inv4  = INV_block()
        self.inv5  = INV_block()
        self.inv6  = INV_block()
        self.inv7  = INV_block()
        self.inv8  = INV_block()
        self.inv9  = INV_block()
        self.inv10 = INV_block()
        self.inv11 = INV_block()
        self.inv12 = INV_block()
        self.inv13 = INV_block()
        self.inv14 = INV_block()
        self.inv15 = INV_block()
        self.inv16 = INV_block()
        self._blocks = [
            self.inv1,  self.inv2,  self.inv3,  self.inv4,
            self.inv5,  self.inv6,  self.inv7,  self.inv8,
            self.inv9,  self.inv10, self.inv11, self.inv12,
            self.inv13, self.inv14, self.inv15, self.inv16,
        ]

    def forward(self, x, rev: bool = False):
        blocks = self._blocks if not rev else reversed(self._blocks)
        for blk in blocks:
            x = blk(x, rev=rev)
        return x


class _Model(nn.Module):
    """Thin wrapper that holds the Hinet (mirrors HiNetcp/model.py Model)."""
    def __init__(self):
        super().__init__()
        self.model = _Hinet()

    def forward(self, x, rev: bool = False):
        return self.model(x, rev=rev)


# ---------------------------------------------------------------------------
# HiNetSteganography — drop-in wrapper with the same API as INNSteganography
# ---------------------------------------------------------------------------

class HiNetSteganography(nn.Module):
    """
    Wraps HiNet with encode / decode methods compatible with INNSteganography.

    Forward (encode):
        cover_dwt  = DWT(cover)   # [B, 12, H/2, W/2]
        secret_dwt = DWT(secret)  # [B, 12, H/2, W/2]
        output     = net(cat(cover_dwt, secret_dwt))   # [B, 24, H/2, W/2]
        stego      = IWT(output[:, :12])               # [B, 3, H, W]
        z          = output[:, 12:]                    # [B, 12, H/2, W/2]  ← key

    Inverse (decode):
        steg_dwt = DWT(stego)
        output   = net(cat(steg_dwt, z_or_noise), rev=True)
        secret   = IWT(output[:, 12:])
    """

    def __init__(self):
        super().__init__()
        self.dwt = _DWT()
        self.iwt = _IWT()
        self._backbone = _Model()   # named _backbone so load_weights can prefix keys
        self._weights_loaded = False

    # ── encode / decode ────────────────────────────────────────────────────

    def encode(self, cover: torch.Tensor, secret: torch.Tensor):
        """Returns (stego [B,3,H,W], z [B,12,H/2,W/2])."""
        device = next(self.parameters()).device
        cover  = cover.to(device)
        secret = secret.to(device)
        cover_w  = self.dwt(cover)
        secret_w = self.dwt(secret)
        x   = torch.cat([cover_w, secret_w], dim=1)   # [B, 24, H/2, W/2]
        out = self._backbone(x)
        steg_w = out[:, :_SPLIT]                       # [B, 12, H/2, W/2]
        z      = out[:, _SPLIT:]                       # [B, 12, H/2, W/2]
        stego  = self.iwt(steg_w)                      # [B, 3,  H,   W  ]
        return stego, z

    def decode(self, stego: torch.Tensor, z: torch.Tensor = None) -> torch.Tensor:
        """Returns secret [B,3,H,W].

        z : tensor from encode() for exact recovery, or None for approximate.
        """
        device = next(self.parameters()).device
        stego  = stego.to(device)
        steg_w = self.dwt(stego)                       # [B, 12, H/2, W/2]
        if z is None:
            z = torch.randn_like(steg_w)
        else:
            z = z.to(device)
        x_rev   = torch.cat([steg_w, z], dim=1)        # [B, 24, H/2, W/2]
        out_rev = self._backbone(x_rev, rev=True)
        secret_w = out_rev[:, _SPLIT:]                 # [B, 12, H/2, W/2]
        return self.iwt(secret_w)                      # [B, 3,  H,   W  ]

    # ── weight management ──────────────────────────────────────────────────

    def load_weights(self, path: str, map_location=None) -> None:
        """Load a checkpoint produced by HiNetcp/train.py.

        Supported checkpoint formats
        ----------------------------
        1. ``{'net': state_dict, 'opt': ...}``  — standard train.py format
        2. A raw ``state_dict``

        DataParallel 'module.' prefixes are stripped automatically.
        """
        if map_location is None:
            map_location = "cuda" if torch.cuda.is_available() else "cpu"
        ckpt = torch.load(path, map_location=map_location, weights_only=False)
        if isinstance(ckpt, dict) and "net" in ckpt:
            state_dict = ckpt["net"]
        elif isinstance(ckpt, dict):
            state_dict = ckpt
        else:
            raise ValueError("Unsupported checkpoint format")

        # Strip DataParallel wrapper prefix
        state_dict = {
            (k[len("module."):] if k.startswith("module.") else k): v
            for k, v in state_dict.items()
            if "tmp_var" not in k
        }

        # Keys in the checkpoint are like  "model.inv1.r.conv1.weight"
        # Our attribute is self._backbone  → prefix with "_backbone."
        remapped = {"_backbone." + k: v for k, v in state_dict.items()}

        missing, unexpected = self.load_state_dict(remapped, strict=False)
        if missing:
            print(f"[HiNet] {len(missing)} missing key(s): {missing[:3]}", flush=True)
        if unexpected:
            print(f"[HiNet] {len(unexpected)} unexpected key(s): {unexpected[:3]}", flush=True)
        self._weights_loaded = True
        print("[HiNet] Weights loaded successfully.", flush=True)

    @classmethod
    def load(cls, weights_path: str = None) -> "HiNetSteganography":
        """Create a HiNetSteganography, optionally loading pre-trained weights."""
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = cls()
        if weights_path and os.path.isfile(weights_path):
            model.load_weights(weights_path, map_location=str(device))
        else:
            # Deterministic small-scale random init (mirrors HiNetcp/model.py init_model
            # which uses init_scale=0.01 to keep coupling exponentials stable at start).
            torch.manual_seed(2024)
            for m in model.modules():
                if isinstance(m, nn.Conv2d):
                    nn.init.normal_(m.weight, mean=0.0, std=0.01)
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)
        model = model.to(device)
        model.eval()
        if device.type == "cuda":
            print(f"[HiNet] Using GPU: {torch.cuda.get_device_name(device)}", flush=True)
        else:
            print("[HiNet] Using CPU (no CUDA device found).", flush=True)
        return model


# ---------------------------------------------------------------------------
# PIL ↔ Tensor helpers  (identical to inn_model.py so app.py can use either)
# ---------------------------------------------------------------------------

def pil_to_tensor(img: Image.Image) -> torch.Tensor:
    arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)


def tensor_to_pil(t: torch.Tensor) -> Image.Image:
    arr = t.squeeze(0).permute(1, 2, 0).detach().cpu().numpy()
    return Image.fromarray((np.clip(arr, 0.0, 1.0) * 255).astype(np.uint8))


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Building HiNet model …")
    m = HiNetSteganography.load()
    cover  = torch.rand(1, 3, 64, 64)
    secret = torch.rand(1, 3, 64, 64)
    with torch.no_grad():
        stego, z = m.encode(cover, secret)
        secret_back = m.decode(stego, z)
    print(f"cover  shape : {cover.shape}")
    print(f"stego  shape : {stego.shape}")
    print(f"z      shape : {z.shape}")
    mse = ((secret - secret_back) ** 2).mean().item()
    print(f"Round-trip MSE (with z key): {mse:.6f}")
    print("✓ HiNet encode/decode OK" if mse < 1e-6 else f"⚠ MSE higher than expected: {mse}")
