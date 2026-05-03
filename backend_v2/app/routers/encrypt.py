"""
图像加密/解密 API 路由
基于 Logistic 混沌映射
"""
import io
import json
from datetime import datetime
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, Depends, File, UploadFile, Form, HTTPException, status
from fastapi.responses import StreamingResponse
from PIL import Image
import numpy as np
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import User, Task, TaskType
from app.routers.auth import get_current_active_user
from app.ml import (
    encrypt_image, decrypt_image, 
    information_entropy, npcr, uaci
)
from app.utils import (
    bytes_to_pil, pil_to_b64, pil_to_tensor, tensor_to_pil,
    resize_if_needed, ensure_even,
    save_image_to_file, get_task_output_dir, create_task_record_data
)
from app.schemas import EncryptRequest, EncryptResponse, DecryptRequest

settings = get_settings()
router = APIRouter(prefix="/api/encrypt", tags=["加密"])


def save_task_to_db(
    db: Session,
    task_type: TaskType,
    user_id: Optional[int],
    parameters: dict,
    metrics: dict,
    key_data: dict,
    input_image_path: Optional[str] = None,
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
        input_image_path=input_image_path,
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


@router.post("", response_model=EncryptResponse)
async def encrypt(
    image: UploadFile = File(..., description="要加密的图像"),
    r: float = Form(default=3.9991, ge=3.57, le=4.0),
    x0: float = Form(default=0.37291, ge=0, le=1),
    n0: int = Form(default=500, ge=0),
    rounds: int = Form(default=2, ge=1),
    save_to_history: bool = Form(default=True, description="是否保存到历史记录"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
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
        save_to_history: 是否保存到历史记录
    
    返回:
        encrypted_image: 加密后的图像 (base64)
        key: 加密密钥 (用于解密)
        metrics: 质量指标 (信息熵、NPCR、UACI)
        task_id: 任务ID（如果保存到历史记录）
    """
    try:
        img_bytes = await image.read()
        original_pil = bytes_to_pil(img_bytes)
        img = resize_if_needed(original_pil, max_dim=1024)
        
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
        
        task_id = None
        if save_to_history:
            output_dir = get_task_output_dir(current_user.id)
            
            input_image_path = save_image_to_file(
                img, output_dir, prefix="encrypt_input"
            )
            output_image_path = save_image_to_file(
                enc_pil, output_dir, prefix="encrypt_output"
            )
            
            parameters = {
                "r": r,
                "x0": x0,
                "n0": n0,
                "rounds": rounds,
                "original_filename": image.filename
            }
            
            task = save_task_to_db(
                db=db,
                task_type=TaskType.ENCRYPT,
                user_id=current_user.id,
                parameters=parameters,
                metrics=metrics,
                key_data=key,
                input_image_path=input_image_path,
                output_image_path=output_image_path
            )
            task_id = task.id
        
        result = {
            "encrypted_image": pil_to_b64(enc_pil),
            "key": key,
            "metrics": metrics
        }
        if task_id:
            result["task_id"] = task_id
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"加密失败: {str(e)}"
        )


@router.post("/decrypt")
async def decrypt(
    image: UploadFile = File(..., description="要解密的图像"),
    key: str = Form(..., description="加密密钥 (JSON格式)"),
    save_to_history: bool = Form(default=True, description="是否保存到历史记录"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    解密图像
    
    使用 Logistic 混沌映射进行解密
    
    参数:
        image: 要解密的图像文件
        key: 加密密钥 (JSON格式字符串)
        save_to_history: 是否保存到历史记录
    
    返回:
        decrypted_image: 解密后的图像 (base64)
        task_id: 任务ID（如果保存到历史记录）
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
        
        task_id = None
        if save_to_history:
            output_dir = get_task_output_dir(current_user.id)
            
            input_image_path = save_image_to_file(
                img, output_dir, prefix="decrypt_input"
            )
            output_image_path = save_image_to_file(
                dec_pil, output_dir, prefix="decrypt_output"
            )
            
            parameters = {
                "key_used": True,
                "original_filename": image.filename
            }
            
            task = save_task_to_db(
                db=db,
                task_type=TaskType.DECRYPT,
                user_id=current_user.id,
                parameters=parameters,
                metrics={},
                key_data=key_dict,
                input_image_path=input_image_path,
                output_image_path=output_image_path
            )
            task_id = task.id
        
        result = {
            "decrypted_image": pil_to_b64(dec_pil)
        }
        if task_id:
            result["task_id"] = task_id
        
        return result
    
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
    save_to_history: bool = Form(default=True, description="是否保存到历史记录"),
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    """
    解密图像（直接使用参数）
    
    参数:
        image: 要解密的图像文件
        r, x0, n0, rounds: Logistic 参数
        H, W, C: 原始图像尺寸
        save_to_history: 是否保存到历史记录
    
    返回:
        decrypted_image: 解密后的图像 (base64)
        task_id: 任务ID（如果保存到历史记录）
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
        
        task_id = None
        if save_to_history:
            output_dir = get_task_output_dir(current_user.id)
            
            input_image_path = save_image_to_file(
                img, output_dir, prefix="decrypt_input"
            )
            output_image_path = save_image_to_file(
                dec_pil, output_dir, prefix="decrypt_output"
            )
            
            parameters = {
                "r": r,
                "x0": x0,
                "n0": n0,
                "rounds": rounds,
                "H": H,
                "W": W,
                "C": C,
                "original_filename": image.filename
            }
            
            task = save_task_to_db(
                db=db,
                task_type=TaskType.DECRYPT,
                user_id=current_user.id,
                parameters=parameters,
                metrics={},
                key_data=key,
                input_image_path=input_image_path,
                output_image_path=output_image_path
            )
            task_id = task.id
        
        result = {
            "decrypted_image": pil_to_b64(dec_pil)
        }
        if task_id:
            result["task_id"] = task_id
        
        return result
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"解密失败: {str(e)}"
        )


@router.post("/key/download")
async def download_key_direct(
    key: str = Form(..., description="密钥数据 (JSON格式字符串)"),
    task_type: str = Form(default="encrypt", description="任务类型")
):
    """
    直接下载密钥（无需保存到历史记录）
    
    参数:
        key: 密钥数据 (JSON格式字符串)
        task_type: 任务类型
    
    返回:
        密钥文件下载
    """
    try:
        try:
            key_json = json.loads(key)
            key_str = json.dumps(key_json, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            key_str = key
        
        key_bytes = key_str.encode("utf-8")
        key_io = io.BytesIO(key_bytes)
        
        timestamp = int(datetime.utcnow().timestamp())
        
        return StreamingResponse(
            key_io,
            media_type="application/json",
            headers={
                "Content-Disposition": f"attachment; filename={task_type}_key_{timestamp}.json"
            }
        )
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"生成密钥文件失败: {str(e)}"
        )
