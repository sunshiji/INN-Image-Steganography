"""
文件处理工具函数
用于保存图像、密钥等文件到磁盘
"""
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, Any, Dict

from PIL import Image

from app.config import get_settings

settings = get_settings()


def generate_unique_filename(prefix: str = "", extension: str = "png") -> str:
    """
    生成唯一文件名
    
    参数:
        prefix: 文件名前缀
        extension: 文件扩展名
    
    返回:
        唯一文件名
    """
    timestamp = int(time.time() * 1000)
    if prefix:
        return f"{prefix}_{timestamp}.{extension}"
    return f"{timestamp}.{extension}"


def get_task_output_dir(user_id: Optional[int] = None) -> Path:
    """
    获取任务输出目录
    
    参数:
        user_id: 用户ID（可选）
    
    返回:
        输出目录路径
    """
    base_dir = Path(settings.DATA_DIR) / "outputs"
    
    if user_id:
        output_dir = base_dir / f"user_{user_id}"
    else:
        output_dir = base_dir / "anonymous"
    
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


def save_image_to_file(
    image: Image.Image,
    output_dir: Path,
    prefix: str = "image",
    fmt: str = "PNG"
) -> str:
    """
    保存图像到文件
    
    参数:
        image: PIL图像对象
        output_dir: 输出目录
        prefix: 文件名前缀
        fmt: 图像格式
    
    返回:
        保存的文件路径（相对于DATA_DIR）
    """
    filename = generate_unique_filename(prefix, fmt.lower())
    file_path = output_dir / filename
    
    image.save(file_path, format=fmt)
    
    data_dir = Path(settings.DATA_DIR)
    relative_path = file_path.relative_to(data_dir)
    
    return str(relative_path)


def save_key_to_file(
    key_data: Any,
    output_dir: Path,
    prefix: str = "key"
) -> str:
    """
    保存密钥到JSON文件
    
    参数:
        key_data: 密钥数据（可以是dict或str）
        output_dir: 输出目录
        prefix: 文件名前缀
    
    返回:
        保存的文件路径（相对于DATA_DIR）
    """
    filename = generate_unique_filename(prefix, "json")
    file_path = output_dir / filename
    
    if isinstance(key_data, str):
        try:
            key_json = json.loads(key_data)
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(key_json, f, indent=2, ensure_ascii=False)
        except json.JSONDecodeError:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(key_data)
    else:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(key_data, f, indent=2, ensure_ascii=False)
    
    data_dir = Path(settings.DATA_DIR)
    relative_path = file_path.relative_to(data_dir)
    
    return str(relative_path)


def create_task_record_data(
    task_type: str,
    user_id: Optional[int],
    parameters: Dict[str, Any],
    metrics: Optional[Dict[str, Any]] = None,
    key_data: Optional[Any] = None,
    input_image_path: Optional[str] = None,
    cover_image_path: Optional[str] = None,
    secret_image_path: Optional[str] = None,
    output_image_path: Optional[str] = None,
    status: str = "completed",
    error_message: Optional[str] = None
) -> Dict[str, Any]:
    """
    创建任务记录数据字典
    
    参数:
        task_type: 任务类型
        user_id: 用户ID
        parameters: 任务参数
        metrics: 质量指标
        key_data: 密钥数据
        input_image_path: 输入图像路径
        cover_image_path: 载体图像路径
        secret_image_path: 秘密图像路径
        output_image_path: 输出图像路径
        status: 任务状态
        error_message: 错误信息
    
    返回:
        任务记录数据字典
    """
    record = {
        "task_type": task_type,
        "user_id": user_id,
        "parameters": json.dumps(parameters, ensure_ascii=False) if parameters else None,
        "status": status,
        "error_message": error_message,
    }
    
    if metrics:
        record["psnr"] = metrics.get("psnr") or metrics.get("psnr_cover_stego")
        record["ssim"] = metrics.get("ssim") or metrics.get("ssim_cover_stego")
        record["entropy_original"] = metrics.get("entropy_original")
        record["entropy_encrypted"] = metrics.get("entropy_encrypted")
        record["npcr"] = metrics.get("npcr")
        record["uaci"] = metrics.get("uaci")
    
    if key_data:
        if isinstance(key_data, str):
            record["key_data"] = key_data
        else:
            record["key_data"] = json.dumps(key_data, ensure_ascii=False)
    
    if input_image_path:
        record["input_image_path"] = input_image_path
    if cover_image_path:
        record["cover_image_path"] = cover_image_path
    if secret_image_path:
        record["secret_image_path"] = secret_image_path
    if output_image_path:
        record["output_image_path"] = output_image_path
    
    return record
