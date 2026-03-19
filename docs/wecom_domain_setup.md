# 企业微信域名配置方案

## 问题说明

企业微信要求回调URL必须：
1. 使用域名（不支持IP地址）
2. 使用HTTPS协议（不支持HTTP）

## 解决方案：使用DuckDNS免费域名

### 第一步：注册DuckDNS

1. 访问：https://www.duckdns.org/
2. 使用Google、GitHub或Twitter账号登录
3. 登录后会看到你的token，保存好

### 第二步：创建域名

1. 在DuckDNS页面，输入子域名名称
   - 例如：`ailifeos`
   - 完整域名：`ailifeos.duckdns.org`

2. 填写你的IP地址：
   - `69.63.211.116`

3. 点击"Add Domain"

### 第三步：配置动态DNS更新（可选）

如果你的IP会变化，可以设置自动更新：

**Windows PowerShell脚本：**
```powershell
# 保存为 update_dns.ps1
$domain = "ailifeos"
$token = "your_duckdns_token_here"
$ip = (Invoke-RestMethod -Uri "https://api.ipify.org").Trim()

$url = "https://www.duckdns.org/update?domains=$domain&token=$token&ip=$ip"
Invoke-RestMethod -Uri $url
```

**设置定时任务：**
```powershell
# 每小时更新一次
$trigger = New-ScheduledTaskTrigger -Hourly
$action = New-ScheduledTaskAction -Execute "powershell.exe" -Argument "-File C:\path\to\update_dns.ps1"
Register-ScheduledTask -TaskName "UpdateDuckDNS" -Trigger $trigger -Action $action
```

### 第四步：配置HTTPS（使用Let's Encrypt）

#### 方法1：使用Certbot（推荐）

```bash
# 1. 安装Certbot
# Windows: 下载 https://dl.eff.org/certbot-beta-installer-win32.exe

# 2. 获取证书
certbot certonly --standalone -d ailifeos.duckdns.org

# 3. 证书位置
# C:\Certbot\live\ailifeos.duckdns.org\fullchain.pem
# C:\Certbot\live\ailifeos.duckdns.org\privkey.pem
```

#### 方法2：使用自签名证书（测试用）

```bash
# 生成自签名证书
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes
```

### 第五步：配置FastAPI使用HTTPS

修改 `main.py`：

```python
import ssl

def main():
    """Main entry point for AI Life OS Web Service."""
    setup_logging()

    reload_enabled = os.getenv("AI_LIFE_OS_RELOAD", "0").lower() in {"1", "true", "yes"}
    host = os.getenv("AI_LIFE_OS_HOST", "0.0.0.0")
    port = int(os.getenv("AI_LIFE_OS_PORT", "8443"))  # 使用443端口

    # SSL配置
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.load_cert_chain(
        certfile="path/to/cert.pem",
        keyfile="path/to/key.pem"
    )

    uvicorn.run(
        "web.backend.app:app",
        host=host,
        port=port,
        ssl=ssl_context,
        reload=reload_enabled,
        reload_dirs=["web", "core"] if reload_enabled else None,
    )
```

### 第六步：更新企业微信配置

在企业微信管理后台：
1. 设置API接收URL：`https://ailifeos.duckdns.org:8443/wecom/webhook`
2. 保存并验证

## 替代方案：使用ngrok（更简单）

### 第一步：安装ngrok

1. 访问：https://ngrok.com/
2. 注册账号
3. 下载并安装ngrok

### 第二步：启动ngrok

```bash
# 启动穿透
ngrok http 8000

# 会显示类似：
# Forwarding: https://abc123.ngrok.io -> http://localhost:8000
```

### 第三步：使用ngrok域名

在企业微信管理后台：
1. 设置API接收URL：`https://abc123.ngrok.io/wecom/webhook`
2. 保存并验证

**优点：**
- 自动提供HTTPS
- 无需配置证书
- 立即可用

**缺点：**
- 免费版域名会变化（重启ngrok后）
- 需要保持ngrok运行

## 推荐方案

**测试阶段：** 使用ngrok（最简单）
**生产环境：** 使用DuckDNS + Let's Encrypt（免费且稳定）

## 下一步

1. 选择一个方案实施
2. 获得域名后更新企业微信配置
3. 测试验证

详细说明请参考：`docs/wecom_setup_guide.md`
