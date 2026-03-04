# INN-Image-Steganography

基于可逆神经网络（INN）+ Logistic 混沌加密的图像隐写系统。

---

## 部署步骤

### 第一步：获取代码

```bash
cd /home/sunshiji/sys
git clone https://github.com/sunshiji/INN-Image-Steganography.git
cd INN-Image-Steganography
```

---

### 第二步：创建专用 conda 环境（推荐）

```bash
# 创建 inn-stego 环境（仅需执行一次）
conda env create -f environment.yml

# 激活环境
conda activate inn-stego
```

> **说明**：`environment.yml` 安装 Python 3.10 + NumPy/SciPy/Pillow/Flask/Gunicorn，
> 不包含 PyTorch（由下一步自动安装，避免 CUDA 版本冲突）。

---

### 第三步：安装 PyTorch（自动检测 CUDA）

```bash
# 确保已激活 inn-stego 环境
conda activate inn-stego

bash setup.sh
```

脚本自动完成：
- 检测服务器 CUDA 版本，安装对应 torch 1.12.1（CUDA 11.3）
- 若无 CUDA，安装 CPU 版
- 若 torch 已存在则跳过

---

### 第四步：配置账号密码

```bash
cp .env.example ~/.inn-stego.env
nano ~/.inn-stego.env       # 修改 SECRET_KEY 和 ADMIN_PASSWORD
chmod 600 ~/.inn-stego.env
```

生成随机 SECRET_KEY：
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

### 第五步：启动服务

**前台运行（调试）：**

```bash
conda activate inn-stego
bash start.sh
```

**后台运行（nohup）：**

```bash
conda activate inn-stego
nohup bash start.sh > ~/inn-stego.log 2>&1 &
tail -f ~/inn-stego.log
```

**systemd 用户服务（推荐，开机自启）：**

```bash
mkdir -p ~/.config/systemd/user
cp inn-stego.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable inn-stego
systemctl --user start  inn-stego

# 允许 SSH 退出后服务继续运行（需 root 执行一次）
sudo loginctl enable-linger $USER
```

---

### 第六步：访问系统

在浏览器中打开（将 `<server-ip>` 替换为实际服务器 IP）：

```
http://<server-ip>:5000
```

→ 跳转到登录页 → 输入 `~/.inn-stego.env` 中设置的账号密码 → 进入主界面

---

## 快速一览（部署示例）

```bash
ssh <user>@<server-ip>
cd /path/to/INN-Image-Steganography
git pull

# 首次部署
conda env create -f environment.yml
conda activate inn-stego
bash setup.sh
cp .env.example ~/.inn-stego.env && nano ~/.inn-stego.env && chmod 600 ~/.inn-stego.env

# 启动
bash start.sh
```

---

## 环境变量（`~/.inn-stego.env`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | `5000` | 监听端口 |
| `SECRET_KEY` | 内置默认 | Flask Session 密钥（**必须修改**） |
| `ADMIN_USERNAME` | `admin` | 登录用户名 |
| `ADMIN_PASSWORD` | `admin123` | 登录密码（**必须修改**） |
| `WORKERS` | `1` | Gunicorn worker 数 |
| `TIMEOUT` | `180` | 请求超时（秒） |
| `LOG_LEVEL` | `info` | 日志级别 |

> ⚠️ **生产环境必须修改 `SECRET_KEY` 和 `ADMIN_PASSWORD`！**

---

## 常用运维命令

```bash
# 查看服务状态
systemctl --user status inn-stego

# 重启服务（修改配置后）
systemctl --user restart inn-stego

# 查看实时日志
journalctl --user -u inn-stego -f

# 更新代码后重启
cd /home/sunshiji/sys/INN-Image-Steganography
git pull
systemctl --user restart inn-stego
```

---

## 项目结构

```
.
├── environment.yml       # conda 环境定义（inn-stego，Python 3.10）
├── .env.example          # 环境变量模板（复制到 ~/.inn-stego.env 后修改）
├── setup.sh              # 安装脚本（安装 PyTorch，自动检测 CUDA）
├── start.sh              # 启动脚本（自动识别 conda/venv/系统 gunicorn）
├── inn-stego.service     # systemd 用户服务单元
├── login.html            # 登录页面
├── index.html            # 系统总览
├── home.html             # 系统首页
├── encode.html           # INN 隐写编码
├── decode.html           # INN 隐写解码
├── encrypt.html          # 混沌加密
├── results.html          # 结果分析
├── gallery.html          # 案例图库
├── settings.html         # 系统设置
└── backend/
    ├── app.py            # Flask 应用（API + 页面 + 认证）
    ├── gunicorn.conf.py  # Gunicorn 生产配置
    ├── inn_model.py      # INN 网络（Haar 小波 + 耦合层）
    ├── logistic_encrypt.py
    └── requirements.txt  # 非 torch 依赖（flask/gunicorn 等）
```
