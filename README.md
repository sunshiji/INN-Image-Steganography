# INN-Image-Steganography

基于可逆神经网络（INN）+ Logistic 混沌加密的图像隐写系统。

## 快速部署

### 1. 安装依赖

```bash
# CPU 版 PyTorch（无需 GPU）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu

# 其余依赖
pip install flask flask-cors pillow numpy scipy gunicorn
```

### 2. 启动服务

**一键启动（推荐）：**

```bash
bash start.sh
```

**自定义密码（推荐生产环境修改）：**

```bash
SECRET_KEY=your-secret-key \
ADMIN_USERNAME=admin \
ADMIN_PASSWORD=YourStrongPassword \
bash start.sh
```

**手动启动（开发模式）：**

```bash
cd backend
python app.py
```

### 3. 访问系统

启动后在 **任意机器的浏览器** 中打开：

```
http://10.109.118.166:5000
```

系统会跳转到登录页，输入账号密码后进入主界面。

### 默认登录账号

| 项目 | 默认值 | 修改方式 |
|------|--------|----------|
| 用户名 | `admin` | 环境变量 `ADMIN_USERNAME` |
| 密码 | `admin123` | 环境变量 `ADMIN_PASSWORD` |
| Session 密钥 | 内置默认 | 环境变量 `SECRET_KEY` |

> ⚠️ **生产环境请务必修改密码和 SECRET_KEY！**

## 项目结构

```
.
├── login.html            # 登录页面（需身份验证才能进入系统）
├── index.html            # 系统总览（所有页面平铺展示）
├── home.html             # 系统首页
├── encrypt.html          # 混沌加密页面
├── encode.html           # INN 隐写编码页面
├── decode.html           # INN 隐写解码页面
├── results.html          # 结果对比页面
├── gallery.html          # 案例库
├── settings.html         # 系统设置
├── start.sh              # 一键启动脚本（gunicorn）
└── backend/
    ├── app.py            # Flask 服务（API + 页面 + 认证）
    ├── logistic_encrypt.py   # Logistic 混沌加密/解密
    ├── inn_model.py          # INN 网络（Haar 小波 + 耦合层）
    ├── requirements.txt      # Python 依赖
    └── README.md             # 详细说明 + API 文档
```
