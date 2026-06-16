"""
图像工具函数
"""
import io
import base64
from typing import Tuple

import numpy as np
from PIL import Image
import torch


def pil_to_tensor(img: Image.Image) -> torch.Tensor:
    """将PIL图像转换为PyTorch张量"""
    arr = np.array(img.convert("RGB"), dtype=np.float32) / 255.0
    return torch.from_numpy(arr).permute(2, 0, 1).unsqueeze(0)


def tensor_to_pil(t: torch.Tensor) -> Image.Image:
    """将PyTorch张量转换为PIL图像"""
    arr = t.squeeze(0).permute(1, 2, 0).detach().cpu().numpy()
    return Image.fromarray((np.clip(arr, 0.0, 1.0) * 255).astype(np.uint8))


def pil_to_b64(img: Image.Image, fmt: str = "PNG") -> str:
    """将PIL图像转换为base64字符串"""
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def b64_to_pil(b64_str: str) -> Image.Image:
    """将base64字符串转换为PIL图像"""
    img_data = base64.b64decode(b64_str)
    return Image.open(io.BytesIO(img_data)).convert("RGB")


def bytes_to_pil(img_bytes: bytes) -> Image.Image:
    """将字节数据转换为PIL图像"""
    return Image.open(io.BytesIO(img_bytes)).convert("RGB")


def ensure_even(img: Image.Image) -> Image.Image:
    """确保图像尺寸为偶数（用于小波变换）"""
    w, h = img.size
    new_w = w if w % 2 == 0 else w - 1
    new_h = h if h % 2 == 0 else h - 1
    if new_w != w or new_h != h:
        return img.resize((new_w, new_h), Image.LANCZOS)
    return img


def resize_to_match(img: Image.Image, target: Image.Image) -> Image.Image:
    """调整图像大小以匹配目标图像"""
    return img.resize(target.size, Image.LANCZOS)


def resize_if_needed(img: Image.Image, max_dim: int = 1024) -> Image.Image:
    """如果图像过大，按比例缩小"""
    w, h = img.size
    if max(w, h) > max_dim:
        scale = max_dim / max(w, h)
        img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
    return ensure_even(img)
