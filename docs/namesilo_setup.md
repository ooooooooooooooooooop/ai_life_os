# NameSilo域名配置指南

## 前提条件

- 已有NameSilo域名
- 服务器IP：69.63.211.116
- 服务端口：8000

## 第一步：配置DNS解析

### 1. 登录NameSilo管理后台

访问：https://www.namesilo.com/account/login

### 2. 进入域名管理

- 点击"Domain Manager"
- 找到你的域名，点击"DNS Records"

### 3. 添加A记录

**选项A：使用子域名（推荐）**

添加以下记录：

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A | wecom | 69.63.211.116 | 7207 |
| A | api | 69.63.211.116 | 7207 |

这样你的域名会是：
- `wecom.yourdomain.com`
- `api.yourdomain.com`

**选项B：使用根域名**

| Type | Host | Value | TTL |
|------|------|-------|-----|
| A | @ | 69.63.211.116 | 7207 |
| A | www | 69.63.211.116 | 7207 |

这样你的域名会是：
- `yourdomain.com`
- `www.yourdomain.com`

### 4. 等待DNS生效

- DNS传播需要10分钟到48小时
- 通常1-2小时内生效
- 可以用以下命令检查：

```bash
# Windows
nslookup wecom.yourdomain.com

# Linux/Mac
dig wecom.yourdomain.com
```

## 第二步：配置HTTPS证书

### 方法1：使用Certbot（推荐）

#### 1. 安装Certbot

**Windows:**
```powershell
# 下载安装器
# https://dl.eff.org/certbot-beta-installer-win32.exe

# 或使用Chocolatey
choco install certbot
```

**Linux:**
```bash
sudo apt-get update
sudo apt-get install certbot
```

#### 2. 获取证书

**方式A：standalone模式（需要临时停止服务）**

```bash
# 停止当前服务
# Ctrl+C

# 获取证书
certbot certonly --standalone -d wecom.yourdomain.com

# 证书位置：
# /etc/letsencrypt/live/wecom.yourdomain.com/fullchain.pem
# /etc/letsencrypt/live/wecom.yourdomain.com/privkey.pem
```

**方式B：webroot模式（服务运行中获取）**

```bash
# 创建webroot目录
mkdir -p /var/www/certbot

# 获取证书
certbot certonly --webroot -w /var/www/certbot -d wecom.yourdomain.com
```

**方式C：DNS验证（推荐，无需开放端口）**

```bash
# 使用DNS验证
certbot certonly --manual --preferred-challenges dns -d wecom.yourdomain.com

# 按提示添加TXT记录到DNS
```

#### 3. 自动续期

```bash
# 测试续期
certbot renew --dry-run

# 添加定时任务自动续期
# Linux crontab:
0 0 1 * * certbot renew --quiet

# Windows Task Scheduler:
# 每月1号运行：certbot renew
```

### 方法2：使用acme.sh（更灵活）

```bash
# 安装acme.sh
curl https://get.acme.sh | sh

# 使用DNS API验证（推荐）
# 以NameSilo为例：
export Namesilo_Key="your_namesilo_api_key"
acme.sh --issue --dns dns_namesilo -d wecom.yourdomain.com

# 安装证书到指定位置
acme.sh --install-cert -d wecom.yourdomain.com \
  --cert-file /path/to/cert.pem \
  --key-file /path/to/key.pem \
  --fullchain-file /path/to/fullchain.pem
```

### 方法3：使用自签名证书（仅测试用）

```bash
# 生成自签名证书
openssl req -x509 -newkey rsa:4096 \
  -keyout key.pem \
  -out cert.pem \
  -days 365 \
  -nodes \
  -subj "/CN=wecom.yourdomain.com"
```

## 第三步：配置FastAPI使用HTTPS

### 1. 修改main.py

```python
import os
import sys
from pathlib import Path
import ssl

import uvicorn

from core.logger import setup_logging

# Add project root to path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    """Main entry point for AI Life OS Web Service."""
    setup_logging()

    reload_enabled = os.getenv("AI_LIFE_OS_RELOAD", "0").lower() in {"1", "true", "yes"}
    host = os.getenv("AI_LIFE_OS_HOST", "0.0.0.0")
    port = int(os.getenv("AI_LIFE_OS_PORT", "443"))  # HTTPS默认端口

    # SSL配置
    ssl_context = None
    if port == 443:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ssl_context.load_cert_chain(
            certfile="/etc/letsencrypt/live/wecom.yourdomain.com/fullchain.pem",
            keyfile="/etc/letsencrypt/live/wecom.yourdomain.com/privkey.pem"
        )

    uvicorn.run(
        "web.backend.app:app",
        host=host,
        port=port,
        ssl=ssl_context,
        reload=reload_enabled,
        reload_dirs=["web", "core"] if reload_enabled else None,
    )


if __name__ == "__main__":
    main()
```

### 2. 或使用环境变量配置

```bash
# 设置环境变量
export AI_LIFE_OS_PORT=443
export AI_LIFE_OS_SSL_CERT=/etc/letsencrypt/live/wecom.yourdomain.com/fullchain.pem
export AI_LIFE_OS_SSL_KEY=/etc/letsencrypt/live/wecom.yourdomain.com/privkey.pem

# 启动服务
python main.py
```

## 第四步：配置防火墙

### Linux (ufw)

```bash
# 允许HTTPS流量
sudo ufw allow 443/tcp

# 检查状态
sudo ufw status
```

### Linux (firewalld)

```bash
# 允许HTTPS
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

### Windows防火墙

```powershell
# 允许443端口入站
New-NetFirewallRule -DisplayName "HTTPS" -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow
```

## 第五步：更新企业微信配置

### 1. 在企业微信管理后台

- 进入应用详情
- 找到"设置API接收"
- 填写URL：`https://wecom.yourdomain.com/wecom/webhook`
- 保存并验证

### 2. 更新配置文件

编辑 `config/wecom.yaml`：

```yaml
corp_id: "你的企业ID"
corp_secret: "你的应用Secret"
agent_id: "你的应用AgentId"
to_user: "@all"
enabled: true
```

## 第六步：测试验证

### 1. 测试HTTPS访问

```bash
# 测试HTTPS
curl https://wecom.yourdomain.com/health

# 应该返回
{"status":"ok","service":"AI Life OS"}
```

### 2. 测试企业微信连接

```bash
python test_wecom_integration.py
```

### 3. 在企业微信中测试

- 打开企业微信App
- 找到应用
- 发送消息测试

## 常见问题

### Q1: DNS未生效怎么办？

A: 等待DNS传播，或使用以下命令检查：
```bash
# 检查DNS解析
nslookup wecom.yourdomain.com

# 或
dig wecom.yourdomain.com
```

### Q2: 证书获取失败？

A: 确保：
- DNS已正确解析到服务器IP
- 80或443端口可访问
- 防火墙已开放相应端口

### Q3: HTTPS访问失败？

A: 检查：
- 证书文件路径是否正确
- 证书文件权限
- 服务是否正常运行

### Q4: 企业微信验证失败？

A: 确保：
- URL格式正确：`https://wecom.yourdomain.com/wecom/webhook`
- 服务正在运行
- 防火墙允许HTTPS流量

## 自动化脚本

创建自动配置脚本：

```bash
#!/bin/bash
# setup_https.sh

DOMAIN="wecom.yourdomain.com"
EMAIL="your-email@example.com"

# 获取证书
certbot certonly --standalone \
  -d $DOMAIN \
  --email $EMAIL \
  --agree-tos \
  --no-eff-email

# 设置自动续期
(crontab -l 2>/dev/null; echo "0 0 1 * * certbot renew --quiet") | crontab -

echo "HTTPS配置完成！"
echo "证书位置：/etc/letsencrypt/live/$DOMAIN/"
```

## 下一步

1. ✅ 配置DNS解析
2. ✅ 获取HTTPS证书
3. ✅ 更新服务配置
4. ✅ 在企业微信后台配置回调URL
5. ✅ 测试验证

详细说明请参考：`docs/wecom_setup_guide.md`
