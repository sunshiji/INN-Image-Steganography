"""
工具函数模块

导出所有子模块中的函数，便于统一导入。
使用方法: from app.utils import pil_to_tensor, verify_password, create_task_record_data
"""

# 图像工具函数 (image_utils.py)
from app.utils.image_utils import (
    pil_to_tensor,
    tensor_to_pil,
    pil_to_b64,
    b64_to_pil,
    bytes_to_pil,
    ensure_even,
    resize_to_match,
    resize_if_needed,
)

# 图像质量评估指标 (metrics.py)
from app.utils.metrics import (
    psnr,
    ssim,
    information_entropy,
    npcr,
    uaci,
    mse,
    rmse,
)

# 安全工具函数 (security.py)
from app.utils.security import (
    verify_password,
    get_password_hash,
    needs_migration,
    create_access_token,
    decode_access_token,
)

# 文件处理工具函数 (file_utils.py) - 新增
from app.utils.file_utils import (
    save_image_to_file,
    save_key_to_file,
    generate_unique_filename,
    get_task_output_dir,
    create_task_record_data,
)

# 完整的导出列表，确保所有函数都能被正确导入
__all__ = [
    # image_utils.py
    "pil_to_tensor",
    "tensor_to_pil",
    "pil_to_b64",
    "b64_to_pil",
    "bytes_to_pil",
    "ensure_even",
    "resize_to_match",
    "resize_if_needed",
    
    # metrics.py
    "psnr",
    "ssim",
    "information_entropy",
    "npcr",
    "uaci",
    "mse",
    "rmse",
    
    # security.py
    "verify_password",
    "get_password_hash",
    "needs_migration",
    "create_access_token",
    "decode_access_token",
    
    # file_utils.py
    "save_image_to_file",
    "save_key_to_file",
    "generate_unique_filename",
    "get_task_output_dir",
    "create_task_record_data",
]
