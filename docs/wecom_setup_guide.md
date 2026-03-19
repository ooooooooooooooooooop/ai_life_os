# 企业微信机器人配置指南

## 概述

AI Life OS 已集成企业微信机器人功能，支持：
- 接收企业微信用户消息
- 自动回复和处理
- 主动推送通知
- 与AI Life OS核心功能联动

## 配置步骤

### 第一步：创建企业微信应用

1. **登录企业微信管理后台**
   - 访问：https://work.weixin.qq.com/
   - 使用管理员账号登录

2. **创建自建应用**
   - 进入"应用管理" → "自建" → "创建应用"
   - 填写应用信息：
     - 应用名称：`AI Life OS`
     - 应用logo：上传图标
     - 可见范围：选择部门或成员

3. **获取应用凭证**
   - 在应用详情页面记录：
     - **AgentId**：例如 `1000002`
     - **Secret**：点击"查看"获取

4. **获取企业ID**
   - "我的企业" → "企业信息" → "企业ID"
   - 例如：`ww1234567890abcdef`

### 第二步：配置回调URL

1. **准备公网访问地址**
   - 你的服务地址：`http://69.63.211.116:8000`
   - 回调URL：`http://69.63.211.116:8000/wecom/webhook`

2. **在企业微信后台配置**
   - 在应用详情页，找到"设置API接收"
   - 填写URL：`http://69.63.211.116:8000/wecom/webhook`
   - 设置Token（可选）：随机字符串，例如 `ai_life_os_token_2026`
   - 设置EncodingAESKey（可选）：点击"随机获取"
   - 点击"保存"

3. **验证配置**
   - 企业微信会发送GET请求验证URL
   - 系统会自动响应验证请求
   - 验证成功后显示"配置成功"

### 第三步：更新配置文件

编辑 `config/wecom.yaml`：

```yaml
# 企业 ID
corp_id: "ww1234567890abcdef"  # 替换为你的企业ID

# 应用 Secret
corp_secret: "your_app_secret_here"  # 替换为你的应用Secret

# 应用 AgentId
agent_id: "1000002"  # 替换为你的AgentId

# 默认推送对象
to_user: "@all"  # 或指定用户ID，如 "zhangsan|lisi"

# 消息加密配置（如果在上一步配置了）
token: "ai_life_os_token_2026"  # 替换为你的Token
encoding_aes_key: "your_encoding_aes_key_here"  # 替换为你的EncodingAESKey

# 启用企业微信接入
enabled: true  # 改为 true
```

### 第四步：重启服务

```bash
# 停止当前服务
# Ctrl+C

# 重新启动服务
python main.py
```

### 第五步：测试验证

1. **测试健康检查**
   ```bash
   curl http://69.63.211.116:8000/health
   ```

2. **测试企业微信连接**
   ```bash
   python test_wecom_integration.py
   ```

3. **在企业微信中测试**
   - 打开企业微信App
   - 找到"AI Life OS"应用
   - 发送消息："今天" 或 "任务"
   - 应该收到回复

## 功能说明

### 支持的指令

- **"今天" / "任务"** - 查询今日任务计划
- **任意文本** - 视为行为上报，AI会处理并回复

### 消息流程

```
用户发送消息 → 企业微信服务器 → Webhook回调 → AI Life OS处理 → 返回回复
```

### 主动推送

系统可以主动向企业微信推送消息：

```python
from interface.notifiers.wecom_notifier import WeComNotifier
from interface.notifiers.base import Notification, NotificationPriority

# 创建通知器
notifier = WeComNotifier()

# 发送简单消息
notifier.send_raw("这是一条测试消息")

# 发送结构化通知
notification = Notification(
    title="任务提醒",
    message="您有一个重要任务需要处理",
    priority=NotificationPriority.HIGH,
    action_required=True
)
notifier.send(notification)
```

## 高级配置

### 消息加密

如果需要更高的安全性，可以启用消息加密：

1. 在企业微信后台配置Token和EncodingAESKey
2. 在配置文件中填写相同的值
3. 系统会自动处理加密/解密

### 可见范围设置

在企业微信后台设置应用的可见范围：
- 可以限制特定部门或成员使用
- 只有可见范围内的用户才能发送消息

### IP白名单

如果企业微信要求配置IP白名单：
- 添加服务器IP：`69.63.211.116`
- 在"企业信息" → "IP白名单"中配置

## 故障排查

### 问题1：URL验证失败

**原因**：服务未启动或网络不通

**解决**：
```bash
# 检查服务状态
curl http://69.63.211.116:8000/health

# 检查端口监听
netstat -an | grep 8000
```

### 问题2：消息无响应

**原因**：配置错误或服务异常

**解决**：
```bash
# 查看日志
tail -f logs/app.log

# 检查配置
cat config/wecom.yaml

# 运行测试
python test_wecom_integration.py
```

### 问题3：无法发送消息

**原因**：access_token获取失败

**解决**：
- 检查corp_id和corp_secret是否正确
- 检查网络是否能访问企业微信API
- 查看日志中的错误信息

## 安全建议

1. **保护Secret安全**
   - 不要将Secret提交到代码仓库
   - 定期更换Secret

2. **限制可见范围**
   - 只允许必要的用户访问应用

3. **启用消息加密**
   - 在生产环境中建议启用

4. **监控异常访问**
   - 定期检查应用的使用情况

## 下一步

配置完成后，你可以：

1. **自定义消息处理逻辑**
   - 编辑 `interface/wecom_bot.py`
   - 实现更复杂的指令处理

2. **集成AI功能**
   - 连接LLM实现智能对话
   - 实现任务管理、日程提醒等功能

3. **设置定时推送**
   - 配置早安问候
   - 定时任务提醒

## 技术支持

如有问题，请查看：
- 项目文档：`docs/`
- 测试脚本：`test_wecom_integration.py`
- 日志文件：`logs/`
