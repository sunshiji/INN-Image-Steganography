# INN-Image-Steganography

基于可逆神经网络（INN）+ Logistic 混沌加密的图像隐写系统。

## 快速部署

### 依赖安装

```bash
# CPU 版 PyTorch（无需 GPU）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install flask flask-cors pillow numpy scipy gunicorn
```

### 本地运行

```bash
cd backend
python app.py
# 浏览器打开 http://localhost:5000
```

### 部署到服务器（任意机器可访问）

```bash
cd backend
gunicorn -w 2 -b 0.0.0.0:5000 app:app
```

然后在**任意机器的浏览器**中打开 `http://<服务器IP>:5000` 即可使用。

> Flask 同时提供前端页面和后端 API，无需额外的 Web 服务器或静态文件配置。

## 项目结构

```
.
├── index.html            # 导航首页
├── home.html             # 系统介绍
├── encrypt.html          # 混沌加密页面
├── encode.html           # INN 隐写编码页面
├── decode.html           # INN 隐写解码页面
├── results.html          # 结果对比页面
├── gallery.html          # 案例库
├── settings.html         # 系统设置
└── backend/
    ├── app.py            # Flask 服务（同时提供 API + 前端页面）
    ├── logistic_encrypt.py   # Logistic 混沌加密/解密
    ├── inn_model.py          # INN 网络（Haar 小波 + 耦合层）
    ├── requirements.txt      # Python 依赖
    └── README.md             # 详细说明 + API 文档
```
