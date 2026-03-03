# INN 图像隐写系统 — 后端说明

## 功能概述

| 功能 | 说明 |
|------|------|
| 混沌加密（Feature 1） | Logistic 混沌映射对秘密图像进行置乱 + 扩散加密，支持多轮加密 |
| INN 隐写编码（Feature 2） | 基于可逆神经网络 (INN) 将加密后的秘密图像隐藏进载体图像 |
| INN 隐写解码 | 从隐写图像中提取并恢复秘密图像（需要 stego_key） |
| 混沌解密 | 使用混沌密钥还原原始秘密图像 |

## 文件结构

```
backend/
├── app.py              # Flask REST API 主入口
├── logistic_encrypt.py # Logistic 混沌加密/解密模块
├── inn_model.py        # INN 网络定义（Haar 小波 + 耦合层）
└── requirements.txt    # Python 依赖
```

## 快速启动

### 1. 安装依赖

```bash
cd backend
pip install -r requirements.txt
# 或安装 CPU 版 PyTorch（更小体积）：
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install flask flask-cors pillow numpy scipy
```

### 2. 启动后端服务

```bash
cd backend
python app.py
# 默认监听 http://localhost:5000
# 可通过环境变量改变端口：PORT=8080 python app.py
```

### 3. 打开前端页面

用任意浏览器直接打开项目根目录下的 `index.html`（所有页面平铺展示），
或单独打开各功能页面：

| 页面 | 地址 |
|------|------|
| 首页 | `home.html` |
| 混沌加密 | `encrypt.html` |
| 隐写编码 | `encode.html` |
| 隐写解码 | `decode.html` |
| 结果对比 | `results.html` |
| 案例库 | `gallery.html` |
| 系统设置 | `settings.html` |

---

## API 文档

所有接口以 `multipart/form-data` 格式提交文件，返回 JSON。

### `GET /api/health`

健康检查。

```json
{"status": "ok", "model": "INN-Stego-v1"}
```

---

### `POST /api/encrypt` — 混沌加密

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `image` | file | — | 待加密的秘密图像 |
| `r` | float | 3.9991 | Logistic 映射参数 r（3 < r ≤ 4） |
| `x0` | float | 0.37291 | 初始值 x₀（0 < x₀ < 1） |
| `n0` | int | 500 | 预热迭代次数 |
| `rounds` | int | 2 | 加密轮数 |

返回：
```json
{
  "encrypted_image": "<base64-PNG>",
  "key": {"r":3.9991,"x0":0.37291,"n0":500,"rounds":2,"H":256,"W":256,"C":3},
  "metrics": {
    "entropy_original": 7.12,
    "entropy_encrypted": 7.99,
    "npcr": 99.62,
    "uaci": 33.45
  }
}
```

---

### `POST /api/decrypt` — 混沌解密

| 参数 | 类型 | 说明 |
|------|------|------|
| `image` | file | 加密图像 |
| `r`, `x0`, `n0`, `rounds`, `H`, `W`, `C` | — | 与加密时相同的密钥参数 |

返回：`{"decrypted_image": "<base64-PNG>"}`

---

### `POST /api/encode` — INN 隐写编码

| 参数 | 类型 | 说明 |
|------|------|------|
| `cover` | file | 载体图像 |
| `secret` | file | 秘密图像（建议先经过混沌加密） |

返回：
```json
{
  "stego_image": "<base64-PNG>",
  "stego_key":   "<base64-npy>",   // 必须保存，用于精确解码
  "metrics": {"psnr_cover_stego": 13.2, "ssim_cover_stego": 0.26}
}
```

> ⚠️ **请务必保存 `stego_key`**，否则解码只能得到近似结果。

---

### `POST /api/decode` — INN 隐写解码

| 参数 | 类型 | 说明 |
|------|------|------|
| `stego` | file | 隐写图像 |
| `stego_key` | string (可选) | encode 返回的 base64 密钥；不提供则近似模式 |

返回：
```json
{
  "secret_image": "<base64-PNG>",
  "mode": "exact"   // 或 "approximate"
}
```

---

### `POST /api/pipeline/encrypt_encode` — 一键加密隐写

同时完成混沌加密 + INN 编码。参数 = `cover` + `secret` + 加密参数（r / x0 / n0 / rounds）。

返回：`encrypted_secret` + `stego_image` + `chaos_key` + `stego_key` + 各阶段指标。

---

### `POST /api/pipeline/decode_decrypt` — 一键提取解密

同时完成 INN 解码 + 混沌解密。参数 = `stego` + `stego_key`（可选）+ 混沌密钥参数。

返回：`extracted_encrypted` + `decrypted_secret` + `mode`。

---

## 工作流程

```
【发送方】
  秘密图像
     │
     ▼
  混沌加密 (r, x0, n0, rounds)
     │  ← 保存 chaos_key（用于接收方解密）
     ▼
  加密图像
     │
     ▼
  INN 隐写编码 (cover + encrypted_secret)
     │  ← 保存 stego_key（用于接收方精确解码）
     ▼
  隐写图像（外观与载体图像几乎一致）

【接收方】
  隐写图像 + stego_key
     │
     ▼
  INN 隐写解码 → 加密图像
     │
     ▼
  混沌解密 (chaos_key) → 原始秘密图像
```

## 技术说明

### Logistic 混沌加密
- 使用 Logistic 混沌序列生成像素置乱索引（scrambling）
- 使用另一段混沌序列与像素值异或（diffusion）
- 支持多轮加密，每轮使用独立的混沌初始值
- 解密为加密的严格逆过程，保证无损还原

### INN 网络结构
- 8 个可逆耦合块（Additive Coupling Layers）
- 每块含一个 ResNet 风格的子网络 F（2层卷积 + LeakyReLU）
- 输入/输出使用 Haar 小波变换（无参数，精确可逆）
- 不需要训练即可运行；提供 stego_key 时解码数学精确

### PSNR / 指标说明
| 指标 | 含义 |
|------|------|
| PSNR(cover, stego) | 隐写图像与载体图像的峰值信噪比（越高越隐蔽） |
| SSIM(cover, stego) | 结构相似性（越接近 1 越好） |
| 信息熵 | 加密图像应接近 8.0（随机性最大） |
| NPCR | 像素变化率（加密前后，>99% 为优） |
| UACI | 平均绝对变化强度（理想值约 33%） |
