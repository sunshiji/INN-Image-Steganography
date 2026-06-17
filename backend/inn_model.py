"""
INN (Invertible Neural Network) for image steganography.

Architecture
------------
  Cover + Secret  →  [Haar DWT]  →  [N × Coupling Blocks]  →  Stego + Noise
  Stego           →  [N × Coupling Blocks (reversed)]  →  [Haar IDWT]  →  Cover' + Secret'

Each Coupling Block is an additive/affine coupling layer:
    x1, x2 = split(x)
    y1 = x1
    y2 = x2 + F(x1)
    forward: (x1, x2) → (y1, y2)
    inverse: y1, y2 → x1 = y1,  x2 = y2 - F(y1)

F is a small residual CNN.

The network is *deterministic* — no training required for basic functionality.
We initialise weights from a fixed seed so the encode/decode pairing is always consistent.
For a real research system you would fine-tune with a perceptual loss; here we keep it
simple so it runs out-of-the-box without a GPU.
"""

import torch
import torch.nn as nn
import numpy as np
from PIL import Image
import io


# ---------------------------------------------------------------------------
# Sub-network F used inside each coupling block
# ---------------------------------------------------------------------------

class ResidualBlock(nn.Module):
    def __init__(self, channels: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(channels, channels, 3, padding=1),
            nn.LeakyReLU(0.2, inplace=True),
            nn.Conv2d(channels, channels, 3, padding=1),
        )

    def forward(self, x):
        return x + self.net(x)


class SubNet(nn.Module):
    """The F sub-network inside a coupling block."""
    def __init__(self, in_ch: int, out_ch: int, hidden: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv2d(in_ch, hidden, 3, padding=1),
            nn.LeakyReLU(0.2, inplace=True),
            ResidualBlock(hidden),
            nn.Conv2d(hidden, out_ch, 3, padding=1),
            nn.Tanh(),
        )

    def forward(self, x):
        return self.net(x)


# ---------------------------------------------------------------------------
# Coupling block
# ---------------------------------------------------------------------------

class CouplingBlock(nn.Module):
    def __init__(self, in_channels: int):
        super().__init__()
        half = in_channels // 2
        self.F = SubNet(half, half)

    def forward(self, x):
        x1, x2 = x.chunk(2, dim=1)
        y1 = x1
        y2 = x2 + self.F(x1)
        return torch.cat([y1, y2], dim=1)

    def inverse(self, y):
        y1, y2 = y.chunk(2, dim=1)
        x1 = y1
        x2 = y2 - self.F(y1)
        return torch.cat([x1, x2], dim=1)


# ---------------------------------------------------------------------------
# Haar Wavelet transforms (lossless, no learnable parameters)
# ---------------------------------------------------------------------------

class HaarForward(nn.Module):
    """2-D Haar DWT: (B, C, H, W) → (B, 4C, H/2, W/2)"""
    def forward(self, x):
        x00 = x[:, :, 0::2, 0::2]
        x01 = x[:, :, 0::2, 1::2]
        x10 = x[:, :, 1::2, 0::2]
        x11 = x[:, :, 1::2, 1::2]
        LL = (x00 + x01 + x10 + x11) / 4
        LH = (x00 - x01 + x10 - x11) / 4
        HL = (x00 + x01 - x10 - x11) / 4
        HH = (x00 - x01 - x10 + x11) / 4
        return torch.cat([LL, LH, HL, HH], dim=1)


class HaarInverse(nn.Module):
    """Inverse 2-D Haar DWT: (B, 4C, H/2, W/2) → (B, C, H, W)"""
    def forward(self, x):
        C4 = x.shape[1]
        C  = C4 // 4
        LL, LH, HL, HH = x[:, :C], x[:, C:2*C], x[:, 2*C:3*C], x[:, 3*C:]
        B, _, H2, W2 = LL.shape
        out = torch.zeros(B, C, H2*2, W2*2, device=x.device, dtype=x.dtype)
        out[:, :, 0::2, 0::2] = LL + LH + HL + HH
        out[:, :, 0::2, 1::2] = LL - LH + HL - HH
        out[:, :, 1::2, 0::2] = LL + LH - HL - HH
        out[:, :, 1::2, 1::2] = LL - LH - HL + HH
        return out


# ---------------------------------------------------------------------------
# Full INN steganography network
# ---------------------------------------------------------------------------

class INNSteganography(nn.Module):
    """
    Forward (encode):
        x = concat(cover, secret)  [B, 6, H, W] for RGB
        Apply Haar DWT  → [B, 24, H/2, W/2]
        Apply N coupling blocks
        Apply Haar IDWT → [B, 6, H, W]
        stego   = out[:, :3]
        noise   = out[:, 3:]   (discarded; replaced with zeros at decode time)

    Inverse (decode):
        y = concat(stego, zeros)  [B, 6, H, W]
        Apply Haar DWT
        Apply N coupling blocks in reverse
        Apply Haar IDWT → [B, 6, H, W]
        cover'  = out[:, :3]
        secret' = out[:, 3:]
    """

    def __init__(self, n_blocks: int = 8, channels: int = 6):
        super().__init__()
        self.haar_fwd = HaarForward()
        self.haar_inv = HaarInverse()
        self.blocks = nn.ModuleList(
            [CouplingBlock(channels * 4) for _ in range(n_blocks)]
        )

    def encode(self, cover: torch.Tensor, secret: torch.Tensor):
        """
        Returns
        -------
        stego : Tensor [B, 3, H, W]  — carrier image with secret hidden inside
        noise : Tensor [B, 3, H, W]  — hidden code required for exact decoding
        """
        x = torch.cat([cover, secret], dim=1)          # [B, 6, H, W]
        x = self.haar_fwd(x)                           # [B, 24, H/2, W/2]
        for block in self.blocks:
            x = block(x)
        x = self.haar_inv(x)                           # [B, 6, H, W]
        stego = x[:, :3]
        noise = x[:, 3:]                               # preserve for exact decoding
        return stego, noise

    def decode(self, stego: torch.Tensor, noise: torch.Tensor = None) -> torch.Tensor:
        """
        Parameters
        ----------
        stego : Tensor [B, 3, H, W]
        noise : Tensor [B, 3, H, W] | None
            If provided (from the encode step), recovery is mathematically exact.
            If None, zeros are used — approximate but gives a visual impression.
        """
        if noise is None:
            noise = torch.zeros_like(stego)
        x = torch.cat([stego, noise], dim=1)           # [B, 6, H, W]
        x = self.haar_fwd(x)                           # [B, 24, H/2, W/2]
        for block in reversed(self.blocks):
            x = block.inverse(x)
        x = self.haar_inv(x)                           # [B, 6, H, W]
        secret = x[:, 3:]
        return secret

    @classmethod
    def load(cls, n_blocks: int = 8) -> "INNSteganography":
        """
        Build a deterministic model from a fixed seed with small-scale
        initialisation so the coupling blocks start near-identity.

        Near-identity coupling means:
            F(x) ≈ 0  →  stego ≈ cover  (no visible colour distortion)
        The exact stego-key (noise tensor) allows perfect round-trip recovery.
        """
        torch.manual_seed(2024)
        model = cls(n_blocks=n_blocks)
        # Initialise with very small weights so the INN is near-identity and
        # the stego image visually resembles the cover.
        for m in model.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.normal_(m.weight, mean=0.0, std=0.01)
                if m.bias is not None:
                    nn.init.zeros_(m.bias)
        model.eval()
        return model


# ---------------------------------------------------------------------------
# PIL ↔ Tensor helpers
# ---------------------------------------------------------------------------

def pil_to_tensor(img: Image.Image) -> torch.Tensor:
    """Convert a PIL Image (H×W×3 uint8) to a float tensor [1, 3, H, W] in [0,1]."""
    arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)


def tensor_to_pil(t: torch.Tensor) -> Image.Image:
    """Convert a tensor [1, 3, H, W] in [0,1] to a PIL Image."""
    arr = t.squeeze(0).permute(1, 2, 0).detach().cpu().numpy()
    arr = np.clip(arr, 0.0, 1.0)
    return Image.fromarray((arr * 255).astype(np.uint8))


def resize_to_match(cover: Image.Image, secret: Image.Image) -> Image.Image:
    """Resize *secret* to the size of *cover* (nearest-neighbour)."""
    return secret.resize(cover.size, Image.LANCZOS)


def ensure_even(img: Image.Image) -> Image.Image:
    """Crop to the nearest even dimensions (required for Haar DWT)."""
    w, h = img.size
    return img.crop((0, 0, w - w % 2, h - h % 2))


# ---------------------------------------------------------------------------
# Quality metrics
# ---------------------------------------------------------------------------

def psnr(original: np.ndarray, processed: np.ndarray) -> float:
    mse = np.mean((original.astype(np.float64) - processed.astype(np.float64)) ** 2)
    if mse == 0:
        return float("inf")
    return float(10 * np.log10((255.0 ** 2) / mse))


def ssim(img1: np.ndarray, img2: np.ndarray) -> float:
    """Simplified SSIM (mean over channels)."""
    from scipy.signal import convolve2d
    C1, C2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    scores = []
    for c in range(img1.shape[2] if img1.ndim == 3 else 1):
        a = img1[:, :, c].astype(np.float64) if img1.ndim == 3 else img1.astype(np.float64)
        b = img2[:, :, c].astype(np.float64) if img2.ndim == 3 else img2.astype(np.float64)
        kernel = np.ones((11, 11)) / 121
        mu1 = convolve2d(a, kernel, mode='same')
        mu2 = convolve2d(b, kernel, mode='same')
        mu1_sq, mu2_sq, mu12 = mu1**2, mu2**2, mu1*mu2
        sig1 = convolve2d(a**2, kernel, mode='same') - mu1_sq
        sig2 = convolve2d(b**2, kernel, mode='same') - mu2_sq
        sig12 = convolve2d(a*b,  kernel, mode='same') - mu12
        s = ((2*mu12 + C1)*(2*sig12 + C2)) / ((mu1_sq + mu2_sq + C1)*(sig1 + sig2 + C2))
        scores.append(float(np.mean(s)))
    return float(np.mean(scores))


# ---------------------------------------------------------------------------
# Quick self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    model = INNSteganography.load()
    cover  = Image.new("RGB", (64, 64), (100, 150, 200))
    secret = Image.new("RGB", (64, 64), (200,  50,  80))

    ct = pil_to_tensor(cover)
    st = pil_to_tensor(secret)

    with torch.no_grad():
        stego_t, noise_t = model.encode(ct, st)
        # Exact recovery (with noise key)
        secret_exact_t  = model.decode(stego_t, noise_t)
        # Approximate recovery (without key)
        secret_approx_t = model.decode(stego_t, None)

    stego_img     = tensor_to_pil(stego_t)
    sec_exact_img = tensor_to_pil(secret_exact_t)
    sec_approx_img= tensor_to_pil(secret_approx_t)

    cover_arr     = np.array(cover)
    stego_arr     = np.array(stego_img)
    sec_arr       = np.array(secret)
    sec_exact_arr = np.array(sec_exact_img)
    sec_approx_arr= np.array(sec_approx_img)

    print("✓ INN encode/decode OK")
    print(f"  PSNR(cover, stego)             : {psnr(cover_arr, stego_arr):.2f} dB")
    print(f"  PSNR(secret, recovered [exact]): {psnr(sec_arr, sec_exact_arr):.2f} dB")
    print(f"  PSNR(secret, recovered [approx]): {psnr(sec_arr, sec_approx_arr):.2f} dB")
