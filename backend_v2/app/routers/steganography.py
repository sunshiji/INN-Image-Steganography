"""
图像隐写 API 路由
基于 HiNet 可逆神经网络
"""
import io
import base64
import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

import numpy as np
import torch
from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from PIL import Image
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User, Task, TaskType
from app.routers.auth import get_current_active_user
from app.ml import (
    get_hinet_model, is_model_loaded, encrypt_image, decrypt_image,
    get_current_model_info, clear_model_cache, list_available_models
)
from app.utils import (
    bytes_to_pil, pil_to_b64, b64_to_pil,
    pil_to_tensor, tensor_to_pil,
    resize_if_needed, ensure_even, resize_to_match,
    psnr, ssim,
    save_image_to_file, get_task_output_dir, create_task_record_data
)
from app.schemas import EncodeResponse, DecodeResponse

settings = get_settings()
router = APIRouter(prefix="/api/steganography", tags=["隐写"])


def save_task_to_db(
    db: Session,
    task_type: TaskType,
    user_id: Optional[int],
    parameters: dict,
    metrics: dict,
    key_data: Optional[str] = None,
    cover_image_path: Optional[str] = None,
    secret_image_path: Optional[str] = None,
    output_image_path: Optional[str] = None,
    status: str = "completed",
    error_message: Optional[str] = None
) -> Task:
    """
    保存任务记录到数据库
    """
    task_data = create_task_record_data(
        task_type=task_type.value,
        user_id=user_id,
        parameters=parameters,
        metrics=metrics,
        key_data=key_data,
        cover_image_path=cover_image_path,
        secret_image_path=secret_image_path,
        output_image_path=output_image_path,
        status=status,
        error_message=error_message
    )
    
    task = Task(**task_data)
    task.completed_at = datetime.utcnow()
    
    db.add(task)
    db.commit()
    db.refresh(task)
    
    return task


def get_model(model_name: Optional[str] = None, force_reload: bool = False):
    """
    获取 HiNet 模型实例
    
    参数:
        model_name: 模型文件名（如 model_best.pt），如果为None则使用默认配置
        force_reload: 是否强制重新加载
    """
    if model_name:
        weights_path = os.path.join(settings.MODEL_DIR, model_name)
        if not os.path.exists(weights_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"模型不存在: {model_name}"
            )
        return get_hinet_model(weights_path, force_reload=force_reload)
    else:
        weights_path = settings.HINET_WEIGHTS_PATH
        return get_hinet_model(weights_path, force_reload=force_reload)


@router.post("/encode", response_model=EncodeResponse)
async def encode(
    cover: UploadFile = File(..., description="载体图像"),
    secret: UploadFile = File(..., description="秘密图像"),
    model_name: Optional[str] = Form(default=None, description="模型文件名（可选，默认使用配置中的模型）"),
    force_reload: bool = Form(default=False, description="是否强制重新加载模型"),
    save_to_history: bool = Form(default=True, description="是否保存到历史记录"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    隐写编码
    
    将秘密图像隐藏到载体图像中，生成隐写图像
    
    参数:
        cover: 载体图像
        secret: 秘密图像
        model_name: 模型文件名（如 model_best.pt，可选，默认使用配置中的模型）
        force_reload: 是否强制重新加载模型
        save_to_history: 是否保存到历史记录
    
    返回:
        stego_image: 隐写图像 (base64)
        stego_key: 解码密钥 (噪声张量 z 的 base64)
        recovery_image: 预计算的恢复图像 (用于验证)
        metrics: 质量指标 (PSNR、SSIM)
        task_id: 任务ID（如果保存到历史记录）
    """
    try:
        model = get_model(model_name, force_reload=force_reload)
        
        cover_bytes = await cover.read()
        secret_bytes = await secret.read()
        
        cover_pil = resize_if_needed(bytes_to_pil(cover_bytes), max_dim=1024)
        secret_pil = ensure_even(resize_to_match(bytes_to_pil(secret_bytes), cover_pil))
        
        cover_t = pil_to_tensor(cover_pil)
        secret_t = pil_to_tensor(secret_pil)
        
        with torch.no_grad():
            stego_t, noise_t = model.encode(cover_t, secret_t)
            secret_rev_t = model.decode(stego_t, noise_t)
        
        stego_pil = tensor_to_pil(stego_t)
        secret_rev_pil = tensor_to_pil(secret_rev_t)
        
        cover_arr = np.array(cover_pil)
        stego_arr = np.array(stego_pil)
        
        metrics = {
            "psnr_cover_stego": round(psnr(cover_arr, stego_arr), 2),
            "ssim_cover_stego": round(ssim(cover_arr, stego_arr), 4),
        }
        
        noise_b64 = _tensor_to_b64(noise_t)
        
        task_id = None
        if save_to_history:
            output_dir = get_task_output_dir(current_user.id)
            
            cover_image_path = save_image_to_file(
                cover_pil, output_dir, prefix="encode_cover"
            )
            secret_image_path = save_image_to_file(
                secret_pil, output_dir, prefix="encode_secret"
            )
            output_image_path = save_image_to_file(
                stego_pil, output_dir, prefix="encode_stego"
            )
            
            parameters = {
                "model_name": model_name,
                "force_reload": force_reload,
                "cover_filename": cover.filename,
                "secret_filename": secret.filename
            }
            
            task = save_task_to_db(
                db=db,
                task_type=TaskType.ENCODE,
                user_id=current_user.id,
                parameters=parameters,
                metrics=metrics,
                key_data=noise_b64,
                cover_image_path=cover_image_path,
                secret_image_path=secret_image_path,
                output_image_path=output_image_path
            )
            task_id = task.id
        
        result = {
            "stego_image": pil_to_b64(stego_pil),
            "stego_key": noise_b64,
            "recovery_image": pil_to_b64(secret_rev_pil),
            "metrics": metrics
        }
        if task_id:
            result["task_id"] = task_id
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"隐写编码失败: {str(e)}"
        )


@router.post("/decode", response_model=DecodeResponse)
async def decode(
    stego: UploadFile = File(..., description="隐写图像"),
    stego_key: Optional[str] = Form(default=None, description="解码密钥 (可选)"),
    model_name: Optional[str] = Form(default=None, description="模型文件名（可选，默认使用配置中的模型）"),
    force_reload: bool = Form(default=False, description="是否强制重新加载模型"),
    save_to_history: bool = Form(default=True, description="是否保存到历史记录"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    隐写解码
    
    从隐写图像中提取秘密图像
    
    参数:
        stego: 隐写图像
        stego_key: 解码密钥 (可选，提供时为精确解码，否则为近似解码)
        model_name: 模型文件名（如 model_best.pt，可选，默认使用配置中的模型）
        force_reload: 是否强制重新加载模型
        save_to_history: 是否保存到历史记录
    
    返回:
        secret_image: 恢复的秘密图像 (base64)
        mode: 解码模式 ("exact" 或 "approximate")
        task_id: 任务ID（如果保存到历史记录）
    """
    try:
        model = get_model(model_name, force_reload=force_reload)
        
        stego_bytes = await stego.read()
        stego_pil = ensure_even(bytes_to_pil(stego_bytes))
        stego_t = pil_to_tensor(stego_pil)
        
        noise_t = None
        if stego_key:
            try:
                noise_t = _b64_to_tensor(stego_key)
            except Exception as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"密钥格式错误: {str(e)}"
                )
        
        with torch.no_grad():
            secret_t = model.decode(stego_t, noise_t)
        
        secret_pil = tensor_to_pil(secret_t)
        mode = "exact" if noise_t is not None else "approximate"
        
        task_id = None
        if save_to_history:
            output_dir = get_task_output_dir(current_user.id)
            
            input_image_path = save_image_to_file(
                stego_pil, output_dir, prefix="decode_input"
            )
            output_image_path = save_image_to_file(
                secret_pil, output_dir, prefix="decode_output"
            )
            
            parameters = {
                "model_name": model_name,
                "force_reload": force_reload,
                "mode": mode,
                "has_key": stego_key is not None,
                "stego_filename": stego.filename
            }
            
            task = save_task_to_db(
                db=db,
                task_type=TaskType.DECODE,
                user_id=current_user.id,
                parameters=parameters,
                metrics={},
                key_data=stego_key,
                cover_image_path=input_image_path,
                output_image_path=output_image_path
            )
            task_id = task.id
        
        result = {
            "secret_image": pil_to_b64(secret_pil),
            "mode": mode
        }
        if task_id:
            result["task_id"] = task_id
        
        return result
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"隐写解码失败: {str(e)}"
        )


@router.post("/pipeline/encrypt-encode")
async def pipeline_encrypt_encode(
    cover: UploadFile = File(..., description="载体图像"),
    secret: UploadFile = File(..., description="秘密图像"),
    r: float = Form(default=3.9991),
    x0: float = Form(default=0.37291),
    n0: int = Form(default=500),
    rounds: int = Form(default=2),
    model_name: Optional[str] = Form(default=None, description="模型文件名（可选，默认使用配置中的模型）"),
    force_reload: bool = Form(default=False, description="是否强制重新加载模型"),
    save_to_history: bool = Form(default=True, description="是否保存到历史记录"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    流水线：混沌加密 + 隐写编码（一键完成）
    
    参数:
        cover: 载体图像
        secret: 秘密图像
        r, x0, n0, rounds: Logistic 加密参数
        model_name: 模型文件名（如 model_best.pt，可选）
        force_reload: 是否强制重新加载模型
        save_to_history: 是否保存到历史记录
    
    返回:
        encrypted_secret: 加密后的秘密图像
        stego_image: 最终隐写图像
        chaos_key: 混沌加密密钥
        stego_key: 隐写解码密钥
        encrypt_metrics: 加密质量指标
        inn_metrics: 隐写质量指标
        task_id: 任务ID（如果保存到历史记录）
    """
    try:
        model = get_model(model_name, force_reload=force_reload)
        
        cover_bytes = await cover.read()
        secret_bytes = await secret.read()
        
        cover_pil = resize_if_needed(bytes_to_pil(cover_bytes), max_dim=1024)
        secret_pil = ensure_even(resize_to_match(bytes_to_pil(secret_bytes), cover_pil))
        
        secret_arr = np.array(secret_pil)
        enc_arr, chaos_key = encrypt_image(secret_arr, r=r, x0=x0, n0=n0, rounds=rounds)
        enc_pil = Image.fromarray(enc_arr.squeeze())
        
        encrypt_metrics = {
            "entropy_original": round(information_entropy(secret_arr), 4),
            "entropy_encrypted": round(information_entropy(enc_arr), 4),
            "npcr": round(npcr(secret_arr, enc_arr), 4),
            "uaci": round(uaci(secret_arr, enc_arr), 4),
        }
        
        cover_t = pil_to_tensor(cover_pil)
        enc_t = pil_to_tensor(enc_pil)
        
        with torch.no_grad():
            stego_t, noise_t = model.encode(cover_t, enc_t)
        
        stego_pil = tensor_to_pil(stego_t)
        
        cover_arr = np.array(cover_pil)
        stego_arr = np.array(stego_pil)
        
        inn_metrics = {
            "psnr_cover_stego": round(psnr(cover_arr, stego_arr), 2),
            "ssim_cover_stego": round(ssim(cover_arr, stego_arr), 4),
        }
        
        stego_key = _tensor_to_b64(noise_t)
        
        task_id = None
        if save_to_history:
            output_dir = get_task_output_dir(current_user.id)
            
            cover_image_path = save_image_to_file(
                cover_pil, output_dir, prefix="pipeline_cover"
            )
            secret_image_path = save_image_to_file(
                secret_pil, output_dir, prefix="pipeline_secret"
            )
            output_image_path = save_image_to_file(
                stego_pil, output_dir, prefix="pipeline_stego"
            )
            
            combined_key = {
                "chaos_key": chaos_key,
                "stego_key": stego_key
            }
            
            parameters = {
                "r": r,
                "x0": x0,
                "n0": n0,
                "rounds": rounds,
                "model_name": model_name,
                "force_reload": force_reload,
                "cover_filename": cover.filename,
                "secret_filename": secret.filename
            }
            
            combined_metrics = {**encrypt_metrics, **inn_metrics}
            
            task = save_task_to_db(
                db=db,
                task_type=TaskType.PIPELINE_ENCRYPT_ENCODE,
                user_id=current_user.id,
                parameters=parameters,
                metrics=combined_metrics,
                key_data=json.dumps(combined_key),
                cover_image_path=cover_image_path,
                secret_image_path=secret_image_path,
                output_image_path=output_image_path
            )
            task_id = task.id
        
        result = {
            "encrypted_secret": pil_to_b64(enc_pil),
            "stego_image": pil_to_b64(stego_pil),
            "chaos_key": chaos_key,
            "stego_key": stego_key,
            "encrypt_metrics": encrypt_metrics,
            "inn_metrics": inn_metrics
        }
        if task_id:
            result["task_id"] = task_id
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"流水线处理失败: {str(e)}"
        )


@router.post("/pipeline/decode-decrypt")
async def pipeline_decode_decrypt(
    stego: UploadFile = File(..., description="隐写图像"),
    stego_key: Optional[str] = Form(default=None),
    r: float = Form(default=3.9991),
    x0: float = Form(default=0.37291),
    n0: int = Form(default=500),
    rounds: int = Form(default=2),
    model_name: Optional[str] = Form(default=None, description="模型文件名（可选，默认使用配置中的模型）"),
    force_reload: bool = Form(default=False, description="是否强制重新加载模型"),
    save_to_history: bool = Form(default=True, description="是否保存到历史记录"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    流水线：隐写解码 + 混沌解密（一键完成）
    
    参数:
        stego: 隐写图像
        stego_key: 隐写解码密钥 (可选)
        r, x0, n0, rounds: Logistic 解密参数
        model_name: 模型文件名（如 model_best.pt，可选）
        force_reload: 是否强制重新加载模型
        save_to_history: 是否保存到历史记录
    
    返回:
        extracted_encrypted: 提取的加密图像
        decrypted_secret: 最终解密的秘密图像
        mode: 解码模式
        task_id: 任务ID（如果保存到历史记录）
    """
    try:
        model = get_model(model_name, force_reload=force_reload)
        
        stego_bytes = await stego.read()
        stego_pil = ensure_even(bytes_to_pil(stego_bytes))
        stego_t = pil_to_tensor(stego_pil)
        
        noise_t = None
        if stego_key:
            noise_t = _b64_to_tensor(stego_key)
        
        with torch.no_grad():
            secret_enc_t = model.decode(stego_t, noise_t)
        
        secret_enc_pil = tensor_to_pil(secret_enc_t)
        enc_arr = np.array(secret_enc_pil)
        
        chaos_key = {
            "r": r, "x0": x0, "n0": n0, "rounds": rounds,
            "H": enc_arr.shape[0], "W": enc_arr.shape[1], 
            "C": enc_arr.shape[2] if len(enc_arr.shape) == 3 else 1
        }
        
        dec_arr = decrypt_image(enc_arr, chaos_key)
        dec_pil = Image.fromarray(dec_arr.squeeze())
        
        mode = "exact" if noise_t is not None else "approximate"
        
        task_id = None
        if save_to_history:
            output_dir = get_task_output_dir(current_user.id)
            
            input_image_path = save_image_to_file(
                stego_pil, output_dir, prefix="pipeline_decode_input"
            )
            output_image_path = save_image_to_file(
                dec_pil, output_dir, prefix="pipeline_decode_output"
            )
            
            parameters = {
                "r": r,
                "x0": x0,
                "n0": n0,
                "rounds": rounds,
                "model_name": model_name,
                "force_reload": force_reload,
                "mode": mode,
                "has_key": stego_key is not None,
                "stego_filename": stego.filename
            }
            
            task = save_task_to_db(
                db=db,
                task_type=TaskType.PIPELINE_DECODE_DECRYPT,
                user_id=current_user.id,
                parameters=parameters,
                metrics={},
                key_data=stego_key,
                cover_image_path=input_image_path,
                output_image_path=output_image_path
            )
            task_id = task.id
        
        result = {
            "extracted_encrypted": pil_to_b64(secret_enc_pil),
            "decrypted_secret": pil_to_b64(dec_pil),
            "mode": mode
        }
        if task_id:
            result["task_id"] = task_id
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"流水线处理失败: {str(e)}"
        )


@router.post("/key/download")
async def download_key_direct(
    key: str = Form(..., description="密钥数据 (可以是JSON字符串或base64字符串)"),
    task_type: str = Form(default="encode", description="任务类型")
):
    """
    直接下载密钥（无需保存到历史记录）
    特别适用于大尺寸的隐写密钥
    
    参数:
        key: 密钥数据
        task_type: 任务类型
    
    返回:
        密钥文件下载
    """
    try:
        key_str = key
        
        key_bytes = key_str.encode("utf-8")
        key_io = io.BytesIO(key_bytes)
        
        timestamp = int(datetime.utcnow().timestamp())
        
        return StreamingResponse(
            key_io,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={task_type}_key_{timestamp}.txt"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成密钥文件失败: {str(e)}"
        )


def _tensor_to_b64(t: torch.Tensor) -> str:
    """将张量转换为 base64 字符串"""
    buf = io.BytesIO()
    np.save(buf, t.detach().cpu().numpy())
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _b64_to_tensor(s: str) -> torch.Tensor:
    """将 base64 字符串转换为张量"""
    data = base64.b64decode(s)
    arr = np.load(io.BytesIO(data))
    return torch.from_numpy(arr)


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
    """计算像素变化率"""
    diff = (img1 != img2).astype(np.float64)
    return float(np.sum(diff) / diff.size * 100)


def uaci(img1: np.ndarray, img2: np.ndarray) -> float:
    """计算平均变化强度"""
    if img1.dtype != np.float64:
        img1 = img1.astype(np.float64)
    if img2.dtype != np.float64:
        img2 = img2.astype(np.float64)
    
    diff = np.abs(img1 - img2) / 255.0
    return float(np.mean(diff) * 100)
