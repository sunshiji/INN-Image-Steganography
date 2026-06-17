"""
HiNet 隐写模型 - 基于可逆神经网络的图像隐写
完全兼容 HiNetcp/train.py 训练的权重
"""
import os
import threading
from typing import Optional, Tuple, Dict, Any

import numpy as np
import torch
import torch.nn as nn
from PIL import Image


_CLAMP = 2.0
_C = 3
_SPLIT = _C * 4
_INIT_SCALE = 0.01


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


class _Basic(nn.Module):
    """Basic head used inside SAB."""
    def __init__(self, in_planes, out_planes, kernel_size, padding=0, bias=False):
        super().__init__()
        self.out_channels = out_planes
        self.conv = nn.Conv2d(in_planes, out_planes, kernel_size=kernel_size,
                              padding=padding, bias=bias)
        self.relu = nn.ReLU()

    def forward(self, x):
        x = self.conv(x)
        x = self.relu(x)
        return x


class _ChannelPool(nn.Module):
    """ChannelPool: concatenate max-pool and mean-pool across channels."""
    def forward(self, x):
        return torch.cat((torch.max(x, 1)[0].unsqueeze(1),
                          torch.mean(x, 1).unsqueeze(1)), dim=1)


class _SAB(nn.Module):
    """Spatial Attention Block (from HiNetcp/add/res_ab.py)."""
    def __init__(self):
        super().__init__()
        kernel_size = 3
        self.compress = _ChannelPool()
        self.spatial = _Basic(2, 1, kernel_size, padding=(kernel_size - 1) // 2, bias=False)

    def forward(self, x):
        x_compress = self.compress(x)
        x_out = self.spatial(x_compress)
        scale = torch.sigmoid(x_out)
        return x * scale


class _ResidualAttentionBlock(nn.Module):
    """
    Residual Attention Block (完全匹配 HiNetcp/add/res_ab.py 中的 Residual_Attention_Block)
    关键区别：backend_v2 原实现缺少最后的残差连接 x + x5
    """
    def __init__(self, in_channels=6, out_channels=6, bias=True):
        super().__init__()
        kernel_size = 3
        stride = 1
        padding = 1
        layers = []
        layers.append(
            nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, stride=stride, padding=padding, bias=bias))
        layers.append(nn.ReLU(inplace=True))
        layers.append(
            nn.Conv2d(in_channels, out_channels, kernel_size=kernel_size, stride=stride, padding=padding, bias=bias))
        self.res = nn.Sequential(*layers)
        self.sab = _SAB()

    def forward(self, x):
        x1 = x + self.res(x)
        x2 = x1 + self.res(x1)
        x3 = x2 + self.res(x2)
        x3_1 = x1 + x3
        x4 = x3_1 + self.res(x3_1)
        x4_1 = x + x4
        x5 = self.sab(x4_1)
        x5_1 = x + x5
        return x5_1


class _ResidualDenseBlockOut(nn.Module):
    """
    6-conv dense block with Residual Attention Block skip.
    完全匹配 HiNetcp/rrdb_denselayer.py 中的 ResidualDenseBlock_out (0411版本)
    """
    def __init__(self, input: int, output: int, bias: bool = True):
        super().__init__()
        self.conv1 = nn.Conv2d(input,          32,     3, 1, 1, bias=bias)
        self.conv2 = nn.Conv2d(input + 32,     32,     3, 1, 1, bias=bias)
        self.conv3 = nn.Conv2d(input + 64,     32,     3, 1, 1, bias=bias)
        self.conv4 = nn.Conv2d(input + 96,     32,     3, 1, 1, bias=bias)
        self.conv5 = nn.Conv2d(input + 128,    32,     3, 1, 1, bias=bias)
        self.conv6 = nn.Conv2d(input + 160,    output, 3, 1, 1, bias=bias)
        self.res   = _ResidualAttentionBlock(input, output, bias=bias)
        self.lrelu = nn.LeakyReLU(inplace=True)

    def forward(self, x):
        x1 = self.lrelu(self.conv1(x))
        x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
        x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
        x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
        x5 = self.lrelu(self.conv5(torch.cat((x, x1, x2, x3, x4), 1)))
        x6 = self.conv6(torch.cat((x, x1, x2, x3, x4, x5), 1))
        x = self.res(x6)
        return x


class _INVBlock(nn.Module):
    """
    Affine coupling block with ρ, η, φ sub-nets.
    完全匹配 HiNetcp/invblock.py 中的 INV_block
    """
    def __init__(self,
                 subnet_constructor=_ResidualDenseBlockOut,
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

    def e(self, s):
        return torch.exp(self.clamp * 2 * (torch.sigmoid(s) - 0.5))

    def forward(self, x, rev: bool = False):
        x1 = x.narrow(1, 0, self.split_len1)
        x2 = x.narrow(1, self.split_len1, self.split_len2)
        if not rev:
            t2 = self.f(x2)
            y1 = x1 + t2
            s1, t1 = self.r(y1), self.y(y1)
            y2 = self.e(s1) * x2 + t1
        else:
            s1, t1 = self.r(x1), self.y(x1)
            y2 = (x2 - t1) / self.e(s1)
            t2 = self.f(y2)
            y1 = (x1 - t2)
        return torch.cat((y1, y2), 1)


class _Hinet(nn.Module):
    """16-block invertible network (匹配 HiNetcp/hinet.py)."""
    def __init__(self):
        super().__init__()
        self.inv1  = _INVBlock()
        self.inv2  = _INVBlock()
        self.inv3  = _INVBlock()
        self.inv4  = _INVBlock()
        self.inv5  = _INVBlock()
        self.inv6  = _INVBlock()
        self.inv7  = _INVBlock()
        self.inv8  = _INVBlock()
        self.inv9  = _INVBlock()
        self.inv10 = _INVBlock()
        self.inv11 = _INVBlock()
        self.inv12 = _INVBlock()
        self.inv13 = _INVBlock()
        self.inv14 = _INVBlock()
        self.inv15 = _INVBlock()
        self.inv16 = _INVBlock()
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
    """Thin wrapper that holds the Hinet (匹配 HiNetcp/model.py)."""
    def __init__(self):
        super().__init__()
        self.model = _Hinet()

    def forward(self, x, rev: bool = False):
        return self.model(x, rev=rev)


def init_model_weights(mod: nn.Module, device: torch.device):
    """
    初始化模型权重（与 HiNetcp/model.py 中的 init_model 完全一致）
    这对模型性能至关重要！
    """
    for key, param in mod.named_parameters():
        split = key.split('.')
        if param.requires_grad:
            param.data = _INIT_SCALE * torch.randn(param.data.shape).to(device)
            if split[-2] == 'conv5':
                param.data.fill_(0.)


def get_device() -> torch.device:
    """获取可用的设备（优先GPU）"""
    if torch.cuda.is_available():
        device = torch.device("cuda")
        print(f"[HiNet] CUDA available: {torch.cuda.get_device_name(device)}")
        print(f"[HiNet] CUDA device count: {torch.cuda.device_count()}")
        return device
    else:
        print("[HiNet] CUDA not available, using CPU")
        return torch.device("cpu")


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

    def __init__(self, device: Optional[torch.device] = None):
        super().__init__()
        self.device = device if device is not None else get_device()
        self.dwt = _DWT()
        self.iwt = _IWT()
        self._backbone = _Model()
        self._weights_loaded = False
        self._weights_path: Optional[str] = None
        
        init_model_weights(self._backbone, self.device)
        self.to(self.device)
        self.eval()

    def to_device(self, device: torch.device):
        """将模型移动到指定设备"""
        self.device = device
        self.to(device)
        return self

    def encode(self, cover: torch.Tensor, secret: torch.Tensor) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        执行隐写编码
        
        参数:
            cover: 载体图像张量 [B, 3, H, W] (值范围 [0, 1])
            secret: 秘密图像张量 [B, 3, H, W] (值范围 [0, 1])
            
        返回:
            stego: 隐写图像张量 [B, 3, H, W] (值范围 [0, 1])
            z: 噪声张量（解码密钥）[B, 12, H/2, W/2]
        """
        cover = cover.to(self.device)
        secret = secret.to(self.device)
        
        cover_w = self.dwt(cover)
        secret_w = self.dwt(secret)
        
        x = torch.cat([cover_w, secret_w], dim=1)
        
        with torch.no_grad():
            out = self._backbone(x)
        
        steg_w = out[:, :_SPLIT]
        z = out[:, _SPLIT:]
        stego = self.iwt(steg_w)
        
        stego = torch.clamp(stego, 0.0, 1.0)
        
        return stego, z

    def decode(self, stego: torch.Tensor, z: torch.Tensor = None) -> torch.Tensor:
        """
        执行隐写解码
        
        参数:
            stego: 隐写图像张量 [B, 3, H, W] (值范围 [0, 1])
            z: 噪声张量（可选，提供时为精确解码）
            
        返回:
            secret: 恢复的秘密图像张量 [B, 3, H, W] (值范围 [0, 1])
        """
        stego = stego.to(self.device)
        
        steg_w = self.dwt(stego)
        
        if z is None:
            z = torch.randn_like(steg_w).to(self.device)
        else:
            z = z.to(self.device)
        
        x_rev = torch.cat([steg_w, z], dim=1)
        
        with torch.no_grad():
            out_rev = self._backbone(x_rev, rev=True)
        
        secret_w = out_rev[:, _SPLIT:]
        secret = self.iwt(secret_w)
        
        secret = torch.clamp(secret, 0.0, 1.0)
        
        return secret

    def load_weights(self, path: str, strict: bool = True) -> None:
        """
        加载训练好的权重
        
        支持的权重格式:
            1. {'net': state_dict, 'opt': ...}  - 标准 train.py 格式
            2. 原始 state_dict
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"权重文件不存在: {path}")
        
        print(f"[HiNet] Loading weights from: {path}")
        
        ckpt = torch.load(path, map_location=self.device, weights_only=False)
        
        if isinstance(ckpt, dict) and "net" in ckpt:
            state_dict = ckpt["net"]
            print("[HiNet] Found 'net' key in checkpoint")
        elif isinstance(ckpt, dict):
            state_dict = ckpt
            print("[HiNet] Using raw state_dict from checkpoint")
        else:
            raise ValueError("Unsupported checkpoint format")
        
        state_dict = {
            (k[len("module."):] if k.startswith("module.") else k): v
            for k, v in state_dict.items()
            if "tmp_var" not in k
        }
        
        remapped = {"_backbone." + k: v for k, v in state_dict.items()}
        
        missing, unexpected = self.load_state_dict(remapped, strict=strict)
        
        if missing:
            print(f"[HiNet] {len(missing)} missing key(s): {missing[:5]}")
        if unexpected:
            print(f"[HiNet] {len(unexpected)} unexpected key(s): {unexpected[:5]}")
        
        self._weights_loaded = True
        self._weights_path = path
        print(f"[HiNet] Weights loaded successfully from {path}")

    @classmethod
    def load(cls, weights_path: str = None, device: torch.device = None) -> "HiNetSteganography":
        """
        创建 HiNetSteganography 实例，可选加载预训练权重
        """
        if device is None:
            device = get_device()
        
        model = cls(device=device)
        
        if weights_path and os.path.isfile(weights_path):
            model.load_weights(weights_path)
        else:
            print(f"[HiNet] No weights provided, using initialized weights on {device}")
        
        return model

    @property
    def is_weights_loaded(self) -> bool:
        """检查是否已加载权重"""
        return self._weights_loaded

    @property
    def weights_path(self) -> Optional[str]:
        """获取当前加载的权重路径"""
        return self._weights_path


_model_cache: Dict[str, HiNetSteganography] = {}
_model_lock = threading.Lock()
_current_model_path: Optional[str] = None


def get_hinet_model(weights_path: str = None, force_reload: bool = False) -> HiNetSteganography:
    """
    获取 HiNet 模型实例（支持缓存和动态切换）
    
    参数:
        weights_path: 权重文件路径，如果为None则使用默认配置
        force_reload: 是否强制重新加载模型（即使已缓存）
    """
    global _model_cache, _current_model_path
    
    with _model_lock:
        if weights_path is None:
            from app.config import get_settings
            settings = get_settings()
            weights_path = settings.HINET_WEIGHTS_PATH
        
        cache_key = weights_path if weights_path else "default"
        
        if force_reload or cache_key not in _model_cache:
            print(f"[HiNet] Loading model: {cache_key}")
            _model_cache[cache_key] = HiNetSteganography.load(weights_path)
        
        _current_model_path = weights_path
        return _model_cache[cache_key]


def is_model_loaded() -> bool:
    """检查模型是否已加载"""
    global _model_cache
    return len(_model_cache) > 0


def get_current_model_info() -> Dict[str, Any]:
    """获取当前模型的信息"""
    global _current_model_path, _model_cache
    
    info = {
        "current_weights_path": _current_model_path,
        "cached_models": list(_model_cache.keys()),
        "device": None,
        "weights_loaded": False
    }
    
    if _current_model_path in _model_cache:
        model = _model_cache[_current_model_path]
        info["device"] = str(model.device)
        info["weights_loaded"] = model.is_weights_loaded
    
    return info


def clear_model_cache() -> None:
    """清除模型缓存（用于切换模型时释放内存）"""
    global _model_cache, _current_model_path
    with _model_lock:
        _model_cache.clear()
        _current_model_path = None
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        print("[HiNet] Model cache cleared")


def list_available_models(model_dir: str = None) -> List[Dict[str, Any]]:
    """
    列出指定目录下可用的模型权重文件
    
    参数:
        model_dir: 模型目录，如果为None则使用默认配置
    """
    if model_dir is None:
        from app.config import get_settings
        settings = get_settings()
        model_dir = settings.MODEL_DIR
    
    models = []
    
    if os.path.exists(model_dir):
        for item in os.listdir(model_dir):
            if item.endswith('.pt') or item.endswith('.pth'):
                full_path = os.path.join(model_dir, item)
                stat = os.stat(full_path)
                models.append({
                    "name": item,
                    "path": full_path,
                    "size_bytes": stat.st_size,
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "modified_at": stat.st_mtime
                })
    
    return sorted(models, key=lambda x: x["modified_at"], reverse=True)
