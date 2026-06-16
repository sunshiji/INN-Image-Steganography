"""
图像加密/解密 API 路由
基于 Logistic 混沌映射
"""
import io
import json
from typing import Optional

from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from PIL import Image
import numpy as np

from app.models import User
from app.routers.auth import get_current_active_user
from app.ml import (
    encrypt_image, decrypt_image, 
    information_entropy, npcr, uaci
)
from app.utils import (
    bytes_to_pil, pil_to_b64, pil_to_tensor, tensor_to_pil,
    resize_if_needed, ensure_even
)
from app.schemas import EncryptRequest, EncryptResponse, DecryptRequest

router = APIRouter(prefix="/api/encrypt", tags=["加密"])


@router.post("", response_model=EncryptResponse)
async def encrypt(
    image: UploadFile = File(..., description="要加密的图像"),
    r: float = Form(default=3.9991, ge=3.57, le=4.0),
    x0: float = Form(default=0.37291, ge=0, le=1),
    n0: int = Form(default=500, ge=0),
    rounds: int = Form(default=2, ge=1),
    current_user: User = Depends(get_current_active_user)
):
    """
    加密图像
    
    使用 Logistic 混沌映射进行像素置乱和扩散双重加密
    
    参数:
        image: 要加密的图像文件
        r: Logistic 控制参数 (3.57 < r <= 4)
        x0: 初始值 (0 < x0 < 1)
        n0: 预热步数
        rounds: 加密轮数
    
    返回:
        encrypted_image: 加密后的图像 (base64)
        key: 加密密钥 (用于解密)
        metrics: 质量指标 (信息熵、NPCR、UACI)
    """
    try:
        img_bytes = await image.read()
        img = bytes_to_pil(img_bytes)
        img = resize_if_needed(img, max_dim=1024)
        
        img_arr = np.array(img)
        
        enc_arr, key = encrypt_image(img_arr, r=r, x0=x0, n0=n0, rounds=rounds)
        enc_pil = Image.fromarray(enc_arr.squeeze())
        
        enc_arr_for_metrics = np.array(enc_pil)
        
        metrics = {
            "entropy_original": round(information_entropy(img_arr), 4),
            "entropy_encrypted": round(information_entropy(enc_arr_for_metrics), 4),
            "npcr": round(npcr(img_arr, enc_arr_for_metrics), 4),
            "uaci": round(uaci(img_arr, enc_arr_for_metrics), 4),
        }
        
        return EncryptResponse(
            encrypted_image=pil_to_b64(enc_pil),
            key=key,
            metrics=metrics
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"加密失败: {str(e)}"
        )


@router.post("/decrypt")
async def decrypt(
    image: UploadFile = File(..., description="要解密的图像"),
    key: str = Form(..., description="加密密钥 (JSON格式)"),
    current_user: User = Depends(get_current_active_user)
):
    """
    解密图像
    
    使用 Logistic 混沌映射进行解密
    
    参数:
        image: 要解密的图像文件
        key: 加密密钥 (JSON格式字符串)
    
    返回:
        decrypted_image: 解密后的图像 (base64)
    """
    try:
        img_bytes = await image.read()
        img = bytes_to_pil(img_bytes)
        img_arr = np.array(img)
        
        try:
            key_dict = json.loads(key)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="密钥格式错误，需要 JSON 格式"
            )
        
        dec_arr = decrypt_image(img_arr, key_dict)
        dec_pil = Image.fromarray(dec_arr.squeeze())
        
        return {
            "decrypted_image": pil_to_b64(dec_pil)
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解密失败: {str(e)}"
        )


@router.post("/decrypt/direct")
async def decrypt_direct(
    image: UploadFile = File(..., description="要解密的图像"),
    r: float = Form(default=3.9991),
    x0: float = Form(default=0.37291),
    n0: int = Form(default=500),
    rounds: int = Form(default=2),
    H: int = Form(..., description="原始图像高度"),
    W: int = Form(..., description="原始图像宽度"),
    C: int = Form(default=3, description="原始图像通道数"),
    current_user: User = Depends(get_current_active_user)
):
    """
    解密图像（直接使用参数）
    
    参数:
        image: 要解密的图像文件
        r, x0, n0, rounds: Logistic 参数
        H, W, C: 原始图像尺寸
    
    返回:
        decrypted_image: 解密后的图像 (base64)
    """
    try:
        img_bytes = await image.read()
        img = bytes_to_pil(img_bytes)
        img_arr = np.array(img)
        
        key = {
            "r": r,
            "x0": x0,
            "n0": n0,
            "rounds": rounds,
            "H": H,
            "W": W,
            "C": C
        }
        
        dec_arr = decrypt_image(img_arr, key)
        dec_pil = Image.fromarray(dec_arr.squeeze())
        
        return {
            "decrypted_image": pil_to_b64(dec_pil)
        }
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解密失败: {str(e)}"
        )
