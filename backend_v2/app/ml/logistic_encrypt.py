"""
Logistic 混沌映射图像加密算法
基于像素置乱和扩散的双重加密
"""
from typing import Tuple, Dict, Any

import numpy as np


def logistic_map(r: float, x0: float, n: int, skip: int = 500) -> np.ndarray:
    """
    生成 Logistic 混沌序列
    
    公式: x_{n+1} = r * x_n * (1 - x_n)
    
    参数:
        r: 控制参数 (3.57 < r <= 4)
        x0: 初始值 (0 < x0 < 1)
        n: 需要生成的序列长度
        skip: 舍弃前 skip 个值（消除初始状态影响）
        
    返回:
        混沌序列数组
    """
    total = skip + n
    x = np.zeros(total, dtype=np.float64)
    x[0] = x0
    
    for i in range(total - 1):
        x[i + 1] = r * x[i] * (1 - x[i])
    
    return x[skip:]


def generate_permutation_indices(size: int, r: float, x0: float, skip: int = 500) -> np.ndarray:
    """
    基于混沌序列生成置换索引（用于像素置乱）
    
    参数:
        size: 需要的索引数量
        r: Logistic 参数
        x0: 初始值
        skip: 预热步数
        
    返回:
        置换索引数组
    """
    seq = logistic_map(r, x0, size, skip)
    indices = np.argsort(seq)
    return indices


def scramble_image(img: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """
    使用置换索引对图像进行像素置乱
    
    参数:
        img: 原始图像数组
        indices: 置换索引
        
    返回:
        置乱后的图像
    """
    orig_shape = img.shape
    flat = img.flatten()
    scrambled = flat[indices]
    return scrambled.reshape(orig_shape)


def descramble_image(img: np.ndarray, indices: np.ndarray) -> np.ndarray:
    """
    使用置换索引对图像进行逆置乱（恢复）
    
    参数:
        img: 置乱后的图像
        indices: 原置换索引
        
    返回:
        恢复的图像
    """
    orig_shape = img.shape
    flat = img.flatten()
    reverse_indices = np.argsort(indices)
    descrambled = flat[reverse_indices]
    return descrambled.reshape(orig_shape)


def diffuse_pixels(img: np.ndarray, chaotic_seq: np.ndarray) -> np.ndarray:
    """
    像素扩散（XOR 操作）
    
    参数:
        img: 图像数组
        chaotic_seq: 混沌序列
        
    返回:
        扩散后的图像
    """
    flat = img.flatten().astype(np.uint8)
    seq_uint8 = (chaotic_seq * 255).astype(np.uint8)
    
    if len(seq_uint8) < len(flat):
        seq_uint8 = np.tile(seq_uint8, (len(flat) // len(seq_uint8) + 1))[:len(flat)]
    else:
        seq_uint8 = seq_uint8[:len(flat)]
    
    diffused = np.bitwise_xor(flat, seq_uint8)
    return diffused.reshape(img.shape)


def reverse_diffuse_pixels(img: np.ndarray, chaotic_seq: np.ndarray) -> np.ndarray:
    """
    逆扩散（XOR 是自逆运算）
    """
    return diffuse_pixels(img, chaotic_seq)


def encrypt_image(
    img: np.ndarray,
    r: float = 3.9991,
    x0: float = 0.37291,
    n0: int = 500,
    rounds: int = 2
) -> Tuple[np.ndarray, Dict[str, Any]]:
    """
    加密图像（多轮置乱 + 扩散）
    
    参数:
        img: 原始图像数组 (H, W, C) 或 (H, W)
        r: Logistic 控制参数 (3.57 < r <= 4)
        x0: 初始值 (0 < x0 < 1)
        n0: 预热步数
        rounds: 加密轮数
        
    返回:
        encrypted_img: 加密后的图像
        key: 加密密钥（用于解密）
    """
    orig_shape = img.shape
    total_pixels = int(np.prod(orig_shape))
    
    encrypted = img.astype(np.uint8).copy()
    
    permutation_indices = None
    
    for round_idx in range(rounds):
        if round_idx == 0:
            permutation_indices = generate_permutation_indices(
                total_pixels, r, x0, n0
            )
        
        encrypted = scramble_image(encrypted, permutation_indices)
        
        seq_length = max(total_pixels, 10000)
        chaotic_seq = logistic_map(r, x0 + round_idx * 0.001, seq_length, n0)
        encrypted = diffuse_pixels(encrypted, chaotic_seq)
    
    key = {
        "r": r,
        "x0": x0,
        "n0": n0,
        "rounds": rounds,
        "H": orig_shape[0],
        "W": orig_shape[1],
        "C": orig_shape[2] if len(orig_shape) == 3 else 1,
    }
    
    return encrypted, key


def decrypt_image(
    encrypted_img: np.ndarray,
    key: Dict[str, Any]
) -> np.ndarray:
    """
    解密图像
    
    参数:
        encrypted_img: 加密后的图像
        key: 加密密钥
        
    返回:
        解密后的图像
    """
    r = key["r"]
    x0 = key["x0"]
    n0 = key["n0"]
    rounds = key["rounds"]
    
    orig_shape = (key["H"], key["W"], key["C"]) if key["C"] > 1 else (key["H"], key["W"])
    total_pixels = int(np.prod(orig_shape))
    
    decrypted = encrypted_img.astype(np.uint8).copy()
    
    permutation_indices = generate_permutation_indices(total_pixels, r, x0, n0)
    
    for round_idx in range(rounds - 1, -1, -1):
        seq_length = max(total_pixels, 10000)
        chaotic_seq = logistic_map(r, x0 + round_idx * 0.001, seq_length, n0)
        decrypted = reverse_diffuse_pixels(decrypted, chaotic_seq)
        
        decrypted = descramble_image(decrypted, permutation_indices)
    
    return decrypted.reshape(orig_shape)


def information_entropy(img: np.ndarray) -> float:
    """计算信息熵"""
    if len(img.shape) == 3:
        img = img.mean(axis=2)
    
    hist, _ = np.histogram(img.flatten(), bins=256, range=(0, 256))
    hist = hist.astype(np.float64) / hist.sum()
    
    entropy = 0.0
    for p in hist:
        if p > 0:
            entropy -= p * np.log2(p)
    
    return float(entropy)


def npcr(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算像素变化率 (Number of Pixel Change Rate)"""
    diff = (img1 != img2).astype(np.float64)
    return float(np.sum(diff) / diff.size * 100)


def uaci(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算平均变化强度 (Unified Average Changing Intensity)"""
    if img1.dtype != np.float64:
        img1 = img1.astype(np.float64)
    if img2.dtype != np.float64:
        img2 = img2.astype(np.float64)
    
    diff = np.abs(img1 - img2) / 255.0
    return float(np.mean(diff) * 100)
