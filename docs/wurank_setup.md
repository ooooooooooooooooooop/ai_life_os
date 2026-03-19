# WURANK.TOP 域名配置完成指南

## 当前状态

✅ **DNS解析已正确配置**
- 域名：ailife.wurank.top
- IP地址：69.63.211.116
- 状态：解析正确

## 下一步：配置HTTPS证书

### 方案1：使用Certbot（推荐）

#### Windows安装Certbot

**方法A：使用安装器**
1. 下载：https://dl.eff.org/certbot-beta-installer-win32.exe
2. 运行安装器
3. 安装完成后重启命令行

**方法B：使用Chocolatey**
```powershell
choco install certbot -y
```

#### 获取证书

```powershell
# 停止当前服务（如果8000端口被占用）
# Ctrl+C

# 获取证书（standalone模式）
certbot certonly --standalone -d ailife.wurank.top

# 证书将保存在：
# C:\Certbot\live\ailife.wurank.top\fullchain.pem
# C:\Certbot\live\ailife.wurank.top\privkey.pem
```

#### 自动续期

```powershell
# 创建续期任务
certbot renew --dry-run

# 设置Windows定时任务
# 每月1号自动续期
```

### 方案2：使用acme.sh（更灵活）

#### 安装acme.sh

```bash
# 使用Git Bash或WSL
curl https://get.acme.sh | sh

# 或手动下载
git clone https://github.com/acmesh-official/acme.sh.git
cd acme.sh
./acme.sh --install
```

#### 获取证书

```bash
# 使用standalone模式
acme.sh --issue -d ailife.wurank.top --standalone

# 或使用webroot模式
acme.sh --issue -d ailife.wurank.top --webroot /path/to/webroot
```

### 方案3：使用自签名证书（仅测试）

```bash
# 生成自签名证书
openssl req -x509 -newkey rsa:4096 \
  -keyout key.pem \
  -out cert.pem \
  -days 365 \
  -nodes \
  -subj "/CN=ailife.wurank.top"

# 证书位置：
# cert.pem
# key.pem
```

⚠️ 注意：自签名证书浏览器会显示不安全警告，仅用于测试。

## 配置FastAPI使用HTTPS

### 方法1：修改main.py

编辑 `main.py`，添加SSL配置：

```python
import os
import sys
from pathlib import Path
import ssl

import uvicorn

from core.logger import setup_logging

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
            certfile="C:/Certbot/live/ailife.wurank.top/fullchain.pem",
            keyfile="C:/Certbot/live/ailife.wurank.top/privkey.pem"
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

### 方法2：使用环境变量

```powershell
# 设置环境变量
$env:AI_LIFE_OS_PORT="443"
$env:AI_LIFE_OS_SSL_CERT="C:/Certbot/live/ailife.wurank.top/fullchain.pem"
$env:AI_LIFE_OS_SSL_KEY="C:/Certbot/live/ailife.wurank.top/privkey.pem"

# 启动服务
python main.py
```

### 方法3：使用Nginx反向代理（推荐生产环境）

#### 安装Nginx

```powershell
# 使用Chocolatey
choco install nginx -y
```

#### 配置Nginx

编辑 `C:\nginx\conf\nginx.conf`：

```nginx
server {
    listen 443 ssl;
    server_name ailife.wurank.top;

    ssl_certificate C:/Certbot/live/ailife.wurank.top/fullchain.pem;
    ssl_certificate_key C:/Certbot/live/ailife.wurank.top/privkey.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# HTTP重定向到HTTPS
server {
    listen 80;
    server_name ailife.wurank.top;
    return 301 https://$server_name$request_uri;
}
```

#### 启动Nginx

```powershell
# 测试配置
nginx -t

# 启动Nginx
start nginx

# 重载配置
nginx -s reload
```

## 配置防火墙

### Windows防火墙

```powershell
# 允许HTTPS流量
New-NetFirewallRule -DisplayName "HTTPS" -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow

# 允许HTTP流量（用于证书获取）
New-NetFirewallRule -DisplayName "HTTP" -Direction Inbound -LocalPort 80 -Protocol TCP -Action Allow
```

## 配置企业微信回调

### 在企业微信管理后台

1. 登录：https://work.weixin.qq.com/
2. 进入应用详情
3. 找到"设置API接收"
4. 填写URL：`https://ailife.wurank.top/wecom/webhook`
5. 保存并验证

### 更新配置文件

编辑 `config/wecom.yaml`：

```yaml
corp_id: "你的企业ID"
corp_secret: "你的应用Secret"
agent_id: "你的应用AgentId"
to_user: "@all"
enabled: true
```

## 测试验证

### 1. 测试HTTPS访问

```powershell
# 测试健康检查
curl https://ailife.wurank.top/health

# 应该返回
{"status":"ok","service":"AI Life OS"}
```

### 2. 测试企业微信连接

```powershell
python test_wecom_integration.py
```

### 3. 在企业微信中测试

- 打开企业微信App
- 找到应用
- 发送消息："今天"
- 应该收到回复

## 完整配置流程

### 快速配置（推荐）

```powershell
# 1. 安装Certbot
choco install certbot -y

# 2. 获取证书
certbot certonly --standalone -d ailife.wurank.top

# 3. 配置防火墙
New-NetFirewallRule -DisplayName "HTTPS" -Direction Inbound -LocalPort 443 -Protocol TCP -Action Allow

# 4. 更新main.py（添加SSL配置）

# 5. 启动服务
python main.py

# 6. 测试
curl https://ailife.wurank.top/health
```

## 常见问题

### Q1: 证书获取失败

**原因**：80端口被占用或防火墙阻止

**解决**：
```powershell
# 检查80端口
netstat -ano | findstr :80

# 临时停止占用80端口的服务
# 或使用webroot模式
certbot certonly --webroot -w C:\webroot -d ailife.wurank.top
```

### Q2: HTTPS访问失败

**原因**：证书路径错误或服务未启动

**解决**：
```powershell
# 检查证书文件
dir C:\Certbot\live\ailife.wurank.top\

# 检查服务状态
netstat -ano | findstr :443
```

### Q3: 企业微信验证失败

**原因**：URL配置错误或服务未运行

**解决**：
- 确认URL：`https://ailife.wurank.top/wecom/webhook`
- 确认服务正在运行
- 检查防火墙设置

## 下一步

1. ✅ DNS解析已正确配置
2. ⏳ 安装Certbot获取HTTPS证书
3. ⏳ 配置FastAPI使用HTTPS
4. ⏳ 在企业微信后台配置回调URL
5. ⏳ 测试验证

## 技术支持

详细文档：
- `docs/namesilo_setup.md`
- `docs/wecom_setup_guide.md`

测试脚本：
- `test_wecom_integration.py`
- `scripts/setup_wecom.py`
