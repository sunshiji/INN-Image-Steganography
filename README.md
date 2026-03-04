# INN-Image-Steganography

基于可逆神经网络（INN）+ Logistic 混沌加密的图像隐写系统。

---

## 部署步骤

### 第一步：获取代码

```bash
git clone https://github.com/sunshiji/INN-Image-Steganography.git
cd INN-Image-Steganography
```

### 第二步：安装环境（只需执行一次）

```bash
bash setup.sh
```

脚本自动完成：
- 创建 Python 虚拟环境（`./venv/`）
- 自动检测 CUDA，安装匹配的 GPU 或 CPU 版 PyTorch
- 安装所有其他 Python 依赖

### 第三步：配置账号

```bash
# 从模板创建凭据文件
cp .env.example ~/.inn-stego.env

# 编辑：修改 SECRET_KEY 和 ADMIN_PASSWORD
nano ~/.inn-stego.env

# 限制文件权限
chmod 600 ~/.inn-stego.env
```

### 第四步：启动服务

**前台运行（调试）：**

```bash
bash start.sh
```

**后台运行（nohup）：**

```bash
nohup bash start.sh > ~/inn-stego.log 2>&1 &
tail -f ~/inn-stego.log   # 查看日志
```

**systemd 用户服务（推荐，开机自启）：**

```bash
mkdir -p ~/.config/systemd/user
cp inn-stego.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable inn-stego
systemctl --user start  inn-stego

# 允许用户退出 SSH 后服务继续运行（需 root 执行一次）
sudo loginctl enable-linger $USER
```

### 第五步：浏览器访问

```
http://<服务器IP>:5000
```

系统自动跳转到登录页 → 输入账号密码 → 进入主界面。

---

## 示例：在服务器 10.109.118.166 上部署

```bash
# SSH 登录服务器
ssh sunshiji@10.109.118.166

# 进入项目目录
cd /home/sunshiji/sys/INN-Image-Steganography

# 安装环境（首次）
bash setup.sh

# 配置凭据
cp .env.example ~/.inn-stego.env
nano ~/.inn-stego.env        # 修改 SECRET_KEY 和 ADMIN_PASSWORD
chmod 600 ~/.inn-stego.env

# 安装 systemd 服务
mkdir -p ~/.config/systemd/user
cp inn-stego.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable inn-stego
systemctl --user start inn-stego
sudo loginctl enable-linger sunshiji
```

Windows 浏览器访问：**`http://10.109.118.166:5000`**

---

## 常用运维命令

```bash
# 查看状态
systemctl --user status inn-stego

# 重启（修改配置后）
systemctl --user restart inn-stego

# 查看实时日志
journalctl --user -u inn-stego -f

# 更新代码后重新部署
git pull
systemctl --user restart inn-stego
```

---

## 环境变量（`~/.inn-stego.env`）

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `PORT` | `5000` | 监听端口 |
| `SECRET_KEY` | 内置默认 | Flask Session 加密密钥（**必须修改**） |
| `ADMIN_USERNAME` | `admin` | 登录用户名 |
| `ADMIN_PASSWORD` | `admin123` | 登录密码（**必须修改**） |
| `WORKERS` | `1` | Gunicorn worker 数 |
| `TIMEOUT` | `180` | 请求超时（秒） |
| `LOG_LEVEL` | `info` | 日志级别 |

> ⚠️ **生产环境必须修改 `SECRET_KEY` 和 `ADMIN_PASSWORD`！**
>
> 生成随机 SECRET_KEY：`python3 -c "import secrets; print(secrets.token_hex(32))"`

---

## 项目结构

```
.
├── login.html            # 登录页面（需身份验证）
├── index.html            # 系统总览
├── home.html             # 系统首页
├── encrypt.html          # 混沌加密
├── encode.html           # INN 隐写编码
├── decode.html           # INN 隐写解码
├── results.html          # 结果分析
├── gallery.html          # 案例图库
├── settings.html         # 系统设置
├── .env.example          # 环境变量模板（复制到 ~/.inn-stego.env 后修改）
├── setup.sh              # 一次性安装脚本
├── start.sh              # 启动脚本
├── inn-stego.service     # systemd 用户服务单元文件
└── backend/
    ├── app.py            # Flask 应用（API + 页面 + 认证）
    ├── gunicorn.conf.py  # Gunicorn 生产配置
    ├── logistic_encrypt.py
    ├── inn_model.py
    └── requirements.txt
```
