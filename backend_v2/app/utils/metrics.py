"""
图像质量评估指标
"""
import math
import numpy as np
from scipy.ndimage import uniform_filter


def psnr(original: np.ndarray, processed: np.ndarray) -> float:
    """计算峰值信噪比 (Peak Signal-to-Noise Ratio)"""
    mse = np.mean((original.astype(np.float32) - processed.astype(np.float32)) ** 2)
    if mse < 1e-10:
        return 100.0
    return 10 * math.log10(255.0 ** 2 / mse)


def ssim(img1: np.ndarray, img2: np.ndarray, win_size: int = 7, K1: float = 0.01, K2: float = 0.03) -> float:
    """
    计算结构相似度指数 (Structural Similarity Index)
    基于 scikit-image 的实现
    """
    if img1.dtype != np.float32:
        img1 = img1.astype(np.float32)
    if img2.dtype != np.float32:
        img2 = img2.astype(np.float32)

    if len(img1.shape) == 3:
        ssim_channels = []
        for i in range(img1.shape[2]):
            ssim_channels.append(ssim(img1[:, :, i], img2[:, :, i], win_size, K1, K2))
        return np.mean(ssim_channels)

    L = 255.0
    C1 = (K1 * L) ** 2
    C2 = (K2 * L) ** 2

    cov_norm = win_size ** 2

    ux = uniform_filter(img1, win_size)
    uy = uniform_filter(img2, win_size)

    uxx = uniform_filter(img1 * img1, win_size)
    uyy = uniform_filter(img2 * img2, win_size)
    uxy = uniform_filter(img1 * img2, win_size)

    vx = (uxx - ux * ux) * cov_norm / (cov_norm - 1)
    vy = (uyy - uy * uy) * cov_norm / (cov_norm - 1)
    vxy = (uxy - ux * uy) * cov_norm / (cov_norm - 1)

    ssim_map = ((2 * ux * uy + C1) * (2 * vxy + C2)) / ((ux ** 2 + uy ** 2 + C1) * (vx + vy + C2))
    return float(np.mean(ssim_map))


def information_entropy(img: np.ndarray) -> float:
    """计算信息熵"""
    if len(img.shape) == 3:
        img = img.mean(axis=2)
    
    hist, _ = np.histogram(img.flatten(), bins=256, range=(0, 256))
    hist = hist.astype(np.float32) / hist.sum()
    
    entropy = 0.0
    for p in hist:
        if p > 0:
            entropy -= p * np.log2(p)
    
    return float(entropy)


def npcr(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算像素变化率 (Number of Pixel Change Rate)"""
    diff = (img1 != img2).astype(np.float32)
    return float(np.sum(diff) / diff.size * 100)


def uaci(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算平均变化强度 (Unified Average Changing Intensity)"""
    if img1.dtype != np.float32:
        img1 = img1.astype(np.float32)
    if img2.dtype != np.float32:
        img2 = img2.astype(np.float32)
    
    diff = np.abs(img1 - img2) / 255.0
    return float(np.mean(diff) * 100)


def mse(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算均方误差 (Mean Squared Error)"""
    return float(np.mean((img1.astype(np.float32) - img2.astype(np.float32)) ** 2))


def rmse(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算均方根误差 (Root Mean Squared Error)"""
    return math.sqrt(mse(img1, img2))
