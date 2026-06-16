"""
HiNet 隐写模型 - 基于可逆神经网络的图像隐写
完全兼容 HiNetcp/train.py 训练的权重
"""
import os
from typing import Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
from PIL import Image


# 常量定义
_CLAMP = 2.0
_C = 3
_SPLIT = _C * 4


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


class _ChannelPool(nn.Module):
    """ChannelPool: concatenate max-pool and mean-pool across channels."""
    def forward(self, x):
        return torch.cat((torch.max(x, 1)[0].unsqueeze(1),
                          torch.mean(x, 1).unsqueeze(1)), dim=1)


class _Basic(nn.Module):
    """Basic head used inside SAB."""
    def __init__(self, in_planes, out_planes, kernel_size, padding=0, bias=False):
        super().__init__()
        self.out_channels = out_planes
        self.conv = nn.Conv2d(in_planes, out_planes, kernel_size=kernel_size,
                              padding=padding, bias=bias)
        self.relu = nn.ReLU()

    def forward(self, x):
        return self.relu(self.conv(x))


class _SAB(nn.Module):
    """Spatial Attention Block."""
    def __init__(self):
        super().__init__()
        self.compress = _ChannelPool()
        self.spatial = _Basic(2, 1, kernel_size=3, padding=1, bias=False)

    def forward(self, x):
        return x * torch.sigmoid(self.spatial(self.compress(x)))


class ResidualAttentionBlock(nn.Module):
    """Residual Attention Block."""
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


class ResidualDenseBlockOut(nn.Module):
    """6-conv dense block with Residual Attention Block skip."""
    def __init__(self, input: int, output: int, bias: bool = True):
        super().__init__()
        self.conv1 = nn.Conv2d(input,          32,     3, 1, 1, bias=bias)
        self.conv2 = nn.Conv2d(input + 32,     32,     3, 1, 1, bias=bias)
        self.conv3 = nn.Conv2d(input + 64,     32,     3, 1, 1, bias=bias)
        self.conv4 = nn.Conv2d(input + 96,     32,     3, 1, 1, bias=bias)
        self.conv5 = nn.Conv2d(input + 128,    32,     3, 1, 1, bias=bias)
        self.conv6 = nn.Conv2d(input + 160,    output, 3, 1, 1, bias=bias)
        self.res   = ResidualAttentionBlock(input, output, bias=bias)
        self.lrelu = nn.LeakyReLU(inplace=False)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.lrelu(self.conv5(torch.cat((x, x1, x2, x3, x4), 1)))
        x6 = self.conv6(torch.cat((x, x1, x2, x3, x4, x5), 1))
        return self.res(x6)


class INVBlock(nn.Module):
    """Affine coupling block with ρ, η, φ sub-nets."""
    def __init__(self,
                 subnet_constructor=ResidualDenseBlockOut,
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


class _Hinet(nn.Module):
    """16-block invertible network."""
    def __init__(self):
        super().__init__()
        self.inv1  = INVBlock()
        self.inv2  = INVBlock()
        self.inv3  = INVBlock()
        self.inv4  = INVBlock()
        self.inv5  = INVBlock()
        self.inv6  = INVBlock()
        self.inv7  = INVBlock()
        self.inv8  = INVBlock()
        self.inv9  = INVBlock()
        self.inv10 = INVBlock()
        self.inv11 = INVBlock()
        self.inv12 = INVBlock()
        self.inv13 = INVBlock()
        self.inv14 = INVBlock()
        self.inv15 = INVBlock()
        self.inv16 = INVBlock()
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
    """Thin wrapper that holds the Hinet."""
    def __init__(self):
        super().__init__()
        self.model = _Hinet()

    def forward(self, x, rev: bool = False):
        return self.model(x, rev=rev)


class HiNetSteganography(nn.Module):
    """
    HiNet 隐写模型包装器
    
    编码 (encode):
        cover_dwt  = DWT(cover)
        secret_dwt = DWT(secret)
        output     = net(cat(cover_dwt, secret_dwt))
        stego      = IWT(output[:, :12])
        z          = output[:, 12:]  (解码密钥)
    
    解码 (decode):
        steg_dwt = DWT(stego)
        output   = net(cat(steg_dwt, z_or_noise), rev=True)
        secret   = IWT(output[:, 12:])
    """

    def __init__(self):
        super().__init__()
        self.dwt = _DWT()
        self.iwt = _IWT()
        self._backbone = _Model()
        self._weights_loaded = False

    def encode(self, cover: torch.Tensor, secret: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        执行隐写编码
        
        参数:
            cover: 载体图像张量 [B, 3, H, W]
            secret: 秘密图像张量 [B, 3, H, W]
            
        返回:
            stego: 隐写图像张量 [B, 3, H, W]
            z: 噪声张量（解码密钥）[B, 12, H/2, W/2]
        """
        device = next(self.parameters()).device
        cover = cover.to(device)
        secret = secret.to(device)
        
        cover_w = self.dwt(cover)
        secret_w = self.dwt(secret)
        
        x = torch.cat([cover_w, secret_w], dim=1)
        out = self._backbone(x)
        
        steg_w = out[:, :_SPLIT]
        z = out[:, _SPLIT:]
        stego = self.iwt(steg_w)
        
        return stego, z

    def decode(self, stego: torch.Tensor, z: torch.Tensor = None) -> torch.Tensor:
        """
        执行隐写解码
        
        参数:
            stego: 隐写图像张量 [B, 3, H, W]
            z: 噪声张量（可选，提供时为精确解码）
            
        返回:
            secret: 恢复的秘密图像张量 [B, 3, H, W]
        """
        device = next(self.parameters()).device
        stego = stego.to(device)
        
        steg_w = self.dwt(stego)
        
        if z is None:
            z = torch.randn_like(steg_w)
        else:
            z = z.to(device)
        
        x_rev = torch.cat([steg_w, z], dim=1)
        out_rev = self._backbone(x_rev, rev=True)
        
        secret_w = out_rev[:, _SPLIT:]
        return self.iwt(secret_w)

    def load_weights(self, path: str, map_location=None) -> None:
        """
        加载训练好的权重
        
        支持的权重格式:
            1. {'net': state_dict, 'opt': ...}  - 标准 train.py 格式
            2. 原始 state_dict
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
        
        state_dict = {
            (k[len("module."):] if k.startswith("module.") else k): v
            for k, v in state_dict.items()
            if "tmp_var" not in k
        }
        
        remapped = {"_backbone." + k: v for k, v in state_dict.items()}
        
        missing, unexpected = self.load_state_dict(remapped, strict=False)
        
        if missing:
            print(f"[HiNet] {len(missing)} missing key(s): {missing[:3]}")
        if unexpected:
            print(f"[HiNet] {len(unexpected)} unexpected key(s): {unexpected[:3]}")
        
        self._weights_loaded = True
        print("[HiNet] Weights loaded successfully.")

    @classmethod
    def load(cls, weights_path: str = None) -> "HiNetSteganography":
        """
        创建 HiNetSteganography 实例，可选加载预训练权重
        """
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model = cls()
        
        if weights_path and os.path.isfile(weights_path):
            model.load_weights(weights_path, map_location=str(device))
        else:
            torch.manual_seed(2024)
            for m in model.modules():
                if isinstance(m, nn.Conv2d):
                    nn.init.normal_(m.weight, mean=0.0, std=0.01)
                    if m.bias is not None:
                        nn.init.zeros_(m.bias)
        
        model = model.to(device)
        model.eval()
        
        if device.type == "cuda":
            print(f"[HiNet] Using GPU: {torch.cuda.get_device_name(device)}")
        else:
            print("[HiNet] Using CPU (no CUDA device found).")
        
        return model


# 全局模型实例
_MODEL_INSTANCE: Optional[HiNetSteganography] = None


def get_hinet_model(weights_path: str = None) -> HiNetSteganography:
    """获取全局 HiNet 模型实例（懒加载）"""
    global _MODEL_INSTANCE
    if _MODEL_INSTANCE is None:
        _MODEL_INSTANCE = HiNetSteganography.load(weights_path)
    return _MODEL_INSTANCE


def is_model_loaded() -> bool:
    """检查模型是否已加载"""
    return _MODEL_INSTANCE is not None
