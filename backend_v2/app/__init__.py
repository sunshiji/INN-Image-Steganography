"""
应用包初始化
"""
from app.config import get_settings, Settings
from app.database import get_db, init_db
from app.models import (
    Base,
    User,
    Task,
    TrainingJob,
    TaskType,
    TrainingStatus
)
from app.utils import (
    verify_password, get_password_hash, create_access_token, decode_access_token,
    pil_to_tensor, tensor_to_pil, pil_to_b64, b64_to_pil,
    bytes_to_pil, ensure_even, resize_to_match, resize_if_needed,
    psnr, ssim, information_entropy, npcr, uaci, mse, rmse
)
from app.ml import (
    HiNetSteganography,
    get_hinet_model,
    is_model_loaded,
    encrypt_image,
    decrypt_image,
    HiNetTrainer,
    TrainingConfig,
    get_training_status,
    list_all_training_status,
)

__version__ = "2.0.0"

__all__ = [
    # Config
    "get_settings", "Settings",
    # Database
    "get_db", "init_db",
    # Models
    "Base", "User", "Task", "TrainingJob", "TaskType", "TrainingStatus",
    # Utils
    "verify_password", "get_password_hash", "create_access_token", "decode_access_token",
    "pil_to_tensor", "tensor_to_pil", "pil_to_b64", "b64_to_pil",
    "bytes_to_pil", "ensure_even", "resize_to_match", "resize_if_needed",
    "psnr", "ssim", "information_entropy", "npcr", "uaci", "mse", "rmse",
    # ML
    "HiNetSteganography", "get_hinet_model", "is_model_loaded",
    "encrypt_image", "decrypt_image",
    "HiNetTrainer", "TrainingConfig", "get_training_status", "list_all_training_status",
]
