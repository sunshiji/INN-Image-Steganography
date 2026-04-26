"""
HiNet 模型训练器
支持 Web 界面启动训练、监控进度、保存权重
"""
import json
import math
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torch.optim import Adam
from torch.optim.lr_scheduler import StepLR

from app.config import get_settings
from app.ml.hinet import HiNetSteganography, _Model, _Hinet, INVBlock, ResidualDenseBlockOut
from app.ml.hinet import _DWT, _IWT, _CLAMP, _C, _SPLIT
from app.utils.metrics import psnr as calculate_psnr

settings = get_settings()


# 训练状态管理
_training_lock = threading.Lock()
_training_status: Dict[int, Dict[str, Any]] = {}


class ImageDataset(Dataset):
    """
    图像数据集 - 用于训练和验证
    从指定目录加载所有图像
    """
    
    def __init__(self, root_dir: str, transform=None, image_size: int = 224):
        self.root_dir = Path(root_dir)
        self.transform = transform
        self.image_size = image_size
        
        self.image_paths = []
        for ext in ['*.png', '*.jpg', '*.jpeg', '*.bmp']:
            self.image_paths.extend(list(self.root_dir.glob(ext)))
            self.image_paths.extend(list(self.root_dir.glob(ext.upper())))
        
        print(f"[Dataset] Found {len(self.image_paths)} images in {root_dir}")
    
    def __len__(self):
        return len(self.image_paths)
    
    def __getitem__(self, idx):
        img_path = self.image_paths[idx]
        img = Image.open(img_path).convert('RGB')
        
        if min(img.size) < self.image_size:
            scale = self.image_size / min(img.size)
            new_size = (int(img.size[0] * scale), int(img.size[1] * scale))
            img = img.resize(new_size, Image.LANCZOS)
        
        left = (img.width - self.image_size) // 2
        top = (img.height - self.image_size) // 2
        img = img.crop((left, top, left + self.image_size, top + self.image_size))
        
        img_np = np.array(img, dtype=np.float32) / 255.0
        img_tensor = torch.from_numpy(img_np).permute(2, 0, 1)
        
        return img_tensor


def init_model(mod):
    """初始化模型权重（与 HiNetcp 一致）"""
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    for key, param in mod.named_parameters():
        split = key.split('.')
        if param.requires_grad:
            param.data = 0.01 * torch.randn(param.data.shape).to(device)
            if split[-2] == 'conv5':
                param.data.fill_(0.)


def get_parameter_number(net):
    """计算网络参数数量"""
    total_num = sum(p.numel() for p in net.parameters())
    trainable_num = sum(p.numel() for p in net.parameters() if p.requires_grad)
    return {'Total': total_num, 'Trainable': trainable_num}


def gauss_noise(shape, device):
    """生成高斯噪声"""
    noise = torch.zeros(shape).to(device)
    for i in range(noise.shape[0]):
        noise[i] = torch.randn(noise[i].shape).to(device)
    return noise


class TrainingConfig:
    """训练配置"""
    def __init__(self, **kwargs):
        self.epochs = kwargs.get('epochs', 1000)
        self.batch_size = kwargs.get('batch_size', 8)
        self.learning_rate = kwargs.get('learning_rate', 1e-5)
        self.val_freq = kwargs.get('val_freq', 20)
        self.save_freq = kwargs.get('save_freq', 20)
        
        self.pretrained_weights_path = kwargs.get('pretrained_weights_path', None)
        self.load_optimizer_state = kwargs.get('load_optimizer_state', True)
        
        self.betas = (0.5, 0.999)
        self.weight_decay = 1e-6
        self.weight_step = 50
        self.gamma = 0.5
        
        self.clamp = 2.0
        self.lamda_reconstruction = 5
        self.lamda_guide = 1
        self.lamda_low_frequency = 1


class HiNetTrainer:
    """
    HiNet 模型训练器
    支持后台训练、进度监控、中断恢复、加载预训练权重
    """
    
    def __init__(self, job_id: int, config: TrainingConfig, 
                 train_path: str, val_path: str = None,
                 model_save_dir: str = None):
        self.job_id = job_id
        self.config = config
        self.train_path = train_path
        self.val_path = val_path
        self.model_save_dir = model_save_dir or settings.MODEL_DIR
        
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self._stop_flag = False
        self._is_running = False
        
        self.current_epoch = 0
        self.total_epochs = config.epochs
        self.current_loss = None
        self.best_psnr = 0.0
        self.best_ssim = 0.0
        self.best_loss = float('inf')
        
        self.pretrained_loaded = False
        self.pretrained_path = config.pretrained_weights_path
        
        self.loss_history: List[float] = []
        self.psnr_history: List[float] = []
        self.ssim_history: List[float] = []
        
        os.makedirs(self.model_save_dir, exist_ok=True)
    
    def _update_status(self, **kwargs):
        """更新训练状态"""
        global _training_status
        with _training_lock:
            if self.job_id not in _training_status:
                _training_status[self.job_id] = {}
            _training_status[self.job_id].update(kwargs)
            _training_status[self.job_id]['last_update'] = time.time()
    
    def _load_pretrained_weights(self, net, optim=None):
        """
        加载预训练权重
        支持 HiNetcp 格式: {'net': state_dict, 'opt': optimizer_state, ...}
        """
        if not self.config.pretrained_weights_path:
            return net, optim
        
        weights_path = self.config.pretrained_weights_path
        
        if not os.path.exists(weights_path):
            print(f"[Trainer] Pretrained weights not found: {weights_path}")
            return net, optim
        
        print(f"[Trainer] Loading pretrained weights from: {weights_path}")
        
        try:
            ckpt = torch.load(weights_path, map_location=self.device, weights_only=False)
            
            state_dict = None
            opt_state = None
            
            if isinstance(ckpt, dict):
                if 'net' in ckpt:
                    state_dict = ckpt['net']
                    print("[Trainer] Found 'net' key in checkpoint")
                else:
                    state_dict = ckpt
                
                if 'opt' in ckpt and optim is not None and self.config.load_optimizer_state:
                    opt_state = ckpt['opt']
                    print("[Trainer] Found 'opt' key in checkpoint (optimizer state)")
            else:
                state_dict = ckpt
            
            if state_dict is not None:
                state_dict = {
                    (k[len("module."):] if k.startswith("module.") else k): v
                    for k, v in state_dict.items()
                    if "tmp_var" not in k
                }
                
                if hasattr(net, 'module'):
                    remapped = {"module.model." + k: v for k, v in state_dict.items()}
                else:
                    remapped = {"model." + k: v for k, v in state_dict.items()}
                
                missing, unexpected = net.load_state_dict(remapped, strict=False)
                
                if missing:
                    print(f"[Trainer] {len(missing)} missing key(s): {missing[:5]}")
                if unexpected:
                    print(f"[Trainer] {len(unexpected)} unexpected key(s): {unexpected[:5]}")
                
                self.pretrained_loaded = True
                print(f"[Trainer] Pretrained weights loaded successfully")
            
            if opt_state is not None and optim is not None:
                try:
                    optim.load_state_dict(opt_state)
                    print("[Trainer] Optimizer state loaded from checkpoint")
                except Exception as e:
                    print(f"[Trainer] Failed to load optimizer state: {e}")
            
        except Exception as e:
            print(f"[Trainer] Failed to load pretrained weights: {e}")
            import traceback
            traceback.print_exc()
        
        return net, optim

    def _init_model(self):
        """初始化模型、优化器、损失函数"""
        from app.ml.hinet import _DWT, _IWT
        
        net = _Model()
        net.to(self.device)
        init_model(net)
        
        if torch.cuda.device_count() > 1:
            net = torch.nn.DataParallel(net)
        
        print(f"[Trainer] Model parameters: {get_parameter_number(net)}")
        
        params_trainable = list(filter(lambda p: p.requires_grad, net.parameters()))
        
        optim = Adam(
            params_trainable, 
            lr=self.config.learning_rate,
            betas=self.config.betas,
            eps=1e-6,
            weight_decay=self.config.weight_decay
        )
        
        if self.config.pretrained_weights_path:
            net, optim = self._load_pretrained_weights(net, optim)
        
        scheduler = StepLR(optim, self.config.weight_step, gamma=self.config.gamma)
        
        dwt = _DWT()
        iwt = _IWT()
        
        return net, optim, scheduler, dwt, iwt
    
    def _compute_losses(self, net, cover, secret, dwt, iwt):
        """计算损失函数"""
        cover_input = dwt(cover)
        secret_input = dwt(secret)
        
        input_img = torch.cat((cover_input, secret_input), 1)
        
        output = net(input_img)
        output_steg = output.narrow(1, 0, 4 * _C)
        output_z = output.narrow(1, 4 * _C, output.shape[1] - 4 * _C)
        steg_img = iwt(output_steg)
        
        output_z_guass = gauss_noise(output_z.shape, self.device)
        output_rev = torch.cat((output_steg, output_z_guass), 1)
        output_image = net(output_rev, rev=True)
        
        secret_rev = output_image.narrow(1, 4 * _C, output_image.shape[1] - 4 * _C)
        secret_rev = iwt(secret_rev)
        
        def guide_loss(output, bicubic_image):
            loss_fn = nn.MSELoss(reduce=True, size_average=False)
            return loss_fn(output, bicubic_image)
        
        def reconstruction_loss(rev_input, input):
            loss_fn = nn.MSELoss(reduce=True, size_average=False)
            return loss_fn(rev_input, input)
        
        def low_frequency_loss(ll_input, gt_input):
            loss_fn = nn.MSELoss(reduce=True, size_average=False)
            return loss_fn(ll_input, gt_input)
        
        g_loss = guide_loss(steg_img.to(self.device), cover.to(self.device))
        r_loss = reconstruction_loss(secret_rev, secret)
        steg_low = output_steg.narrow(1, 0, _C)
        cover_low = cover_input.narrow(1, 0, _C)
        l_loss = low_frequency_loss(steg_low, cover_low)
        
        total_loss = (
            self.config.lamda_reconstruction * r_loss + 
            self.config.lamda_guide * g_loss + 
            self.config.lamda_low_frequency * l_loss
        )
        
        return total_loss, steg_img, secret_rev
    
    def _validate(self, net, test_loader, dwt, iwt):
        """验证模型"""
        net.eval()
        psnr_s_list = []
        psnr_c_list = []
        
        with torch.no_grad():
            for x in test_loader:
                x = x.to(self.device)
                cover = x[x.shape[0] // 2:, :, :, :]
                secret = x[:x.shape[0] // 2, :, :, :]
                
                cover_input = dwt(cover)
                secret_input = dwt(secret)
                input_img = torch.cat((cover_input, secret_input), 1)
                
                output = net(input_img)
                output_steg = output.narrow(1, 0, 4 * _C)
                steg = iwt(output_steg)
                output_z = output.narrow(1, 4 * _C, output.shape[1] - 4 * _C)
                output_z = gauss_noise(output_z.shape, self.device)
                
                output_steg = output_steg.to(self.device)
                output_rev = torch.cat((output_steg, output_z), 1)
                output_image = net(output_rev, rev=True)
                secret_rev = output_image.narrow(1, 4 * _C, output_image.shape[1] - 4 * _C)
                secret_rev = iwt(secret_rev)
                
                secret_rev_np = secret_rev.cpu().numpy().squeeze() * 255
                np.clip(secret_rev_np, 0, 255)
                secret_np = secret.cpu().numpy().squeeze() * 255
                np.clip(secret_np, 0, 255)
                cover_np = cover.cpu().numpy().squeeze() * 255
                np.clip(cover_np, 0, 255)
                steg_np = steg.cpu().numpy().squeeze() * 255
                np.clip(steg_np, 0, 255)
                
                psnr_temp = calculate_psnr(secret_rev_np, secret_np)
                psnr_s_list.append(psnr_temp)
                psnr_temp_c = calculate_psnr(cover_np, steg_np)
                psnr_c_list.append(psnr_temp_c)
        
        avg_psnr_s = np.mean(psnr_s_list)
        avg_psnr_c = np.mean(psnr_c_list)
        
        return avg_psnr_s, avg_psnr_c
    
    def start_training(self):
        """开始训练（在后台线程中运行）"""
        if self._is_running:
            return False
        
        self._is_running = True
        self._stop_flag = False
        
        thread = threading.Thread(target=self._train_loop, daemon=True)
        thread.start()
        
        return True
    
    def _train_loop(self):
        """训练主循环"""
        try:
            self._update_status(
                job_id=self.job_id,
                status="running",
                message="Initializing training..."
            )
            
            train_dataset = ImageDataset(self.train_path, image_size=224)
            train_loader = DataLoader(
                train_dataset, 
                batch_size=self.config.batch_size,
                shuffle=True,
                num_workers=0,
                drop_last=True
            )
            
            val_loader = None
            if self.val_path and os.path.exists(self.val_path):
                val_dataset = ImageDataset(self.val_path, image_size=224)
                val_loader = DataLoader(
                    val_dataset,
                    batch_size=2,
                    shuffle=False,
                    num_workers=0
                )
            
            net, optim, scheduler, dwt, iwt = self._init_model()
            
            self._update_status(
                message="Training started",
                total_epochs=self.config.epochs,
                device=str(self.device)
            )
            
            for epoch in range(self.config.epochs):
                if self._stop_flag:
                    self._update_status(status="stopped", message="Training stopped by user")
                    break
                
                self.current_epoch = epoch + 1
                net.train()
                loss_history_epoch = []
                
                for i_batch, data in enumerate(train_loader):
                    if self._stop_flag:
                        break
                    
                    data = data.to(self.device)
                    cover = data[data.shape[0] // 2:]
                    secret = data[:data.shape[0] // 2]
                    
                    optim.zero_grad()
                    
                    total_loss, steg_img, secret_rev = self._compute_losses(
                        net, cover, secret, dwt, iwt
                    )
                    
                    total_loss.backward()
                    optim.step()
                    
                    loss_history_epoch.append(total_loss.item())
                    self.current_loss = total_loss.item()
                    
                    if i_batch % 10 == 0:
                        self._update_status(
                            current_epoch=self.current_epoch,
                            current_batch=i_batch,
                            current_loss=self.current_loss,
                            message=f"Epoch {self.current_epoch}/{self.config.epochs}, Batch {i_batch}"
                        )
                
                epoch_loss = np.mean(loss_history_epoch)
                self.loss_history.append(float(epoch_loss))
                
                if epoch > 0 and epoch % self.config.save_freq == 0:
                    save_path = os.path.join(
                        self.model_save_dir, 
                        f'model_checkpoint_{self.job_id}_{epoch:05d}.pt'
                    )
                    torch.save({
                        'opt': optim.state_dict(),
                        'net': net.state_dict()
                    }, save_path)
                
                if val_loader and epoch % self.config.val_freq == 0:
                    psnr_s, psnr_c = self._validate(net, val_loader, dwt, iwt)
                    self.psnr_history.append(float(psnr_s))
                    
                    if psnr_s > self.best_psnr:
                        self.best_psnr = float(psnr_s)
                        best_path = os.path.join(
                            self.model_save_dir, 
                            f'model_best_{self.job_id}.pt'
                        )
                        torch.save({
                            'opt': optim.state_dict(),
                            'net': net.state_dict()
                        }, best_path)
                    
                    self._update_status(
                        best_psnr=self.best_psnr,
                        message=f"Validation PSNR: {psnr_s:.2f} dB"
                    )
                
                scheduler.step()
            
            if not self._stop_flag:
                final_path = os.path.join(
                    self.model_save_dir, 
                    f'model_final_{self.job_id}.pt'
                )
                torch.save({
                    'opt': optim.state_dict(),
                    'net': net.state_dict()
                }, final_path)
                
                self._update_status(
                    status="completed",
                    message="Training completed successfully",
                    completed_at=datetime.now().isoformat()
                )
        
        except Exception as e:
            import traceback
            self._update_status(
                status="failed",
                message=f"Training failed: {str(e)}",
                error=traceback.format_exc()
            )
        
        finally:
            self._is_running = False
    
    def stop_training(self):
        """停止训练"""
        self._stop_flag = True
    
    def get_status(self) -> Dict[str, Any]:
        """获取当前训练状态"""
        return {
            "job_id": self.job_id,
            "is_running": self._is_running,
            "current_epoch": self.current_epoch,
            "total_epochs": self.total_epochs,
            "current_loss": self.current_loss,
            "best_psnr": self.best_psnr,
            "best_ssim": self.best_ssim,
            "best_loss": self.best_loss,
            "loss_history": self.loss_history[-100:] if self.loss_history else [],
            "psnr_history": self.psnr_history[-100:] if self.psnr_history else [],
        }


def get_training_status(job_id: int) -> Optional[Dict[str, Any]]:
    """获取指定任务的训练状态"""
    with _training_lock:
        return _training_status.get(job_id)


def list_all_training_status() -> Dict[int, Dict[str, Any]]:
    """列出所有训练任务状态"""
    with _training_lock:
        return _training_status.copy()
