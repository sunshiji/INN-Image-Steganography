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

> **说明**：启动时若看到 `[INFO] Port 5000 is in use by PID XXXXXX. Stopping it...`，
> 这是 `start.sh` 在自动停止旧进程，属于正常行为，无需手动处理。

---

### 停止服务

**直接停止（bash stop.sh）：**

```bash
bash stop.sh           # 停止监听 5000 端口的后端进程
PORT=8080 bash stop.sh # 停止其他端口
```

**前台运行时：** 在终端按 `Ctrl+C` 即可。

**nohup 后台运行时：**

```bash
bash stop.sh
```

**systemd 用户服务：**

```bash
systemctl --user stop inn-stego

# 同时禁止开机自启：
systemctl --user disable inn-stego
```

---

### 第六步：开放防火墙端口（**必须**）

服务监听 `0.0.0.0:5000`，但 Ubuntu UFW 防火墙默认会拦截所有外部连接。
**每次部署后必须执行一次**：

```bash
# 方式一：允许所有来源访问 5000 端口（最简单）
sudo ufw allow 5000/tcp
sudo ufw reload

# 方式二：仅允许特定客户端子网（更安全，将 <CLIENT_SUBNET> 替换为实际子网）
sudo ufw allow from <CLIENT_SUBNET> to any port 5000 proto tcp
sudo ufw reload

# 确认规则已生效
sudo ufw status numbered | grep 5000
```

> **验证服务是否可达（在服务器上运行）：**
> ```bash
> bash check.sh
> ```

---

### 第七步：访问系统

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
# 停止后端
bash stop.sh

# 查看服务状态
systemctl --user status inn-stego

# 停止 systemd 服务
systemctl --user stop inn-stego

# 重启服务（修改配置后）
systemctl --user restart inn-stego

# 查看实时日志
journalctl --user -u inn-stego -f

# 更新代码后重启
cd /path/to/INN-Image-Steganography
git pull
systemctl --user restart inn-stego
```

---

## 网络访问故障排查

> 服务已启动（`Listening at: http://0.0.0.0:5000`）但从 Windows 浏览器无法访问？

### 原因一：UFW 防火墙未开放端口（**最常见**）

```bash
# 在服务器上执行：
sudo ufw status        # 查看当前防火墙状态

# 如果是 "Status: active"，需要开放端口：
sudo ufw allow 5000/tcp
sudo ufw reload

# 确认已开放：
sudo ufw status | grep 5000
```

### 原因二：跨子网路由问题

若服务器 IP（如 10.109.x.x）与客户端 IP（如 10.113.x.x）属于不同子网，
需要网络管理员在交换机/路由器上开通两个子网之间的路由。

**临时绕过方案（SSH 端口转发）：**

```bash
# 在 Windows 上打开 PowerShell 或 Git Bash，执行：
ssh -L 5000:127.0.0.1:5000 <user>@<server-ip>

# 然后在浏览器访问：
http://localhost:5000
```

### 原因三：iptables 规则

```bash
# 检查是否有 iptables 规则拦截：
sudo iptables -L INPUT -n --line-numbers | grep -E "DROP|REJECT|5000"

# 如有必要，添加放行规则：
sudo iptables -I INPUT 1 -p tcp --dport 5000 -j ACCEPT
```

### 自动诊断脚本

```bash
# 在服务器上运行，自动检查所有上述项目：
bash check.sh
```

输出示例：
```
[OK]   Service is bound to 0.0.0.0:5000
[OK]   Local request to http://127.0.0.1:5000/ returned HTTP 302
[FAIL] UFW is active but port 5000 is NOT in the allow list
         → FIX: sudo ufw allow 5000/tcp && sudo ufw reload
```

---

## 项目结构

```
.
├── environment.yml       # conda 环境定义（inn-stego，Python 3.10）
├── .env.example          # 环境变量模板（复制到 ~/.inn-stego.env 后修改）
├── setup.sh              # 安装脚本（安装 PyTorch，自动检测 CUDA）
├── start.sh              # 启动脚本（自动识别 conda/venv/系统 gunicorn）
├── stop.sh               # 停止脚本（优雅停止监听指定端口的后端进程）
├── check.sh              # 网络诊断脚本（防火墙/绑定/路由检查）
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
