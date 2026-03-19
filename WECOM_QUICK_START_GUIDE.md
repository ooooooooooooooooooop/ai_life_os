# 企业微信接入功能 - 快速开始指南

## 📋 前置准备

### 1. 企业微信账号
- 您需要有一个企业微信管理员账号
- 有权限在企业微信管理后台创建应用

### 2. 服务器环境
- Python 3.8+
- 已安装依赖：`httpx`、`pyyaml`、`fastapi`
- 公网可访问的服务器（用于接收企业微信回调）

---

## 🚀 快速开始（5 步完成）

### 第 1 步：在企业微信管理后台创建应用

1. **登录企业微信管理后台**
   - 访问：https://work.weixin.qq.com/
   - 使用管理员账号登录

2. **创建应用**
   - 进入"应用管理" → "自建" → "创建应用"
   - 填写应用信息：
     - 应用名称：AI Life OS（或您喜欢的名称）
     - 应用logo：上传应用图标
     - 可见范围：选择需要使用此应用的成员

3. **获取应用信息**
   - 创建完成后，在应用详情页面获取：
     - **AgentId**：应用的唯一标识
     - **Secret**：应用的密钥（点击"查看"获取）

4. **获取企业 ID**
   - 进入"我的企业" → "企业信息"
   - 复制"企业ID"

### 第 2 步：配置回调 URL

1. **设置 API 接收**
   - 在应用详情页面，找到"设置 API 接收"
   - 点击"设置"

2. **填写回调 URL**
   - URL 格式：`https://your-domain.com/wecom/webhook`
   - 例如：`https://ai-life-os.example.com/wecom/webhook`
   - **注意**：必须是 HTTPS 协议，且域名已备案

3. **设置 Token 和 EncodingAESKey（可选）**
   - 如果需要消息加密，填写：
     - Token：任意字符串（如：`ai_life_os_token`）
     - EncodingAESKey：点击"随机获取"
   - 如果不需要加密，可以留空

4. **保存配置**
   - 点击"保存"
   - 企业微信会发送验证请求到您的服务器
   - 如果验证成功，会显示"设置成功"

### 第 3 步：配置 AI Life OS

1. **编辑配置文件**
   ```bash
   # 打开配置文件
   vim config/wecom.yaml
   ```

2. **填写配置信息**
   ```yaml
   # 企业 ID（必填）
   corp_id: "your_corp_id_here"

   # 应用 Secret（必填）
   corp_secret: "your_corp_secret_here"

   # 应用 AgentId（必填）
   agent_id: "your_agent_id_here"

   # 默认推送对象（可选，默认值：@all）
   to_user: "@all"

   # 消息加密 Token（可选，如果配置了加密则填写）
   token: "your_token_here"

   # 消息加密 EncodingAESKey（可选，如果配置了加密则填写）
   encoding_aes_key: "your_encoding_aes_key_here"

   # 是否启用企业微信接入（设置为 true）
   enabled: true
   ```

3. **保存配置文件**

### 第 4 步：启动 AI Life OS

1. **安装依赖（如果未安装）**
   ```bash
   pip install httpx pyyaml fastapi uvicorn
   ```

2. **启动应用**
   ```bash
   # 方式 1：使用 uvicorn 启动
   uvicorn web.backend.app:app --host 0.0.0.0 --port 8000

   # 方式 2：使用 Python 启动
   python -m web.backend.app
   ```

3. **验证启动成功**
   - 访问：`http://your-server-ip:8000/health`
   - 应该返回：`{"status": "ok", "service": "AI Life OS"}`

### 第 5 步：测试功能

1. **运行测试脚本**
   ```bash
   python test_wecom_integration.py
   ```

2. **预期输出**
   ```
   ============================================================
   测试总结
   ============================================================
   通过: 5/5

   [OK] 所有测试通过！
   ```

3. **在企业微信中测试**
   - 打开企业微信客户端
   - 找到您创建的应用
   - 发送消息："你好"
   - 应该收到回复："收到您的消息：你好\n\n系统正在开发中，感谢您的耐心等待！"

---

## 📱 使用示例

### 1. 发送消息给用户

在企业微信应用中发送消息，系统会自动回复：

```
用户：你好
系统：收到您的消息：你好

系统正在开发中，感谢您的耐心等待！
```

### 2. 查询今日任务

```
用户：今天
系统：今日任务计划功能正在开发中，敬请期待！
```

或

```
用户：任务
系统：今日任务计划功能正在开发中，敬请期待！
```

### 3. 接收早安推送

每天 08:00，系统会自动推送早安消息：

```
🌅 早安！新的一天开始了

今日任务计划功能正在开发中，敬请期待！

祝您今天工作顺利！
```

---

## 🔧 高级配置

### 1. 修改定时推送时间

编辑 `scheduler/cron_config.yaml`：

```yaml
- name: wecom-morning-push
  cron: "0 8 * * *"  # 修改为其他时间，如 "30 7 * * *" 表示 07:30
  enabled: true
```

### 2. 禁用定时推送

```yaml
- name: wecom-morning-push
  cron: "0 8 * * *"
  enabled: false  # 设置为 false
```

### 3. 指定推送对象

编辑 `config/wecom.yaml`：

```yaml
# 推送给指定用户
to_user: "zhangsan"

# 推送给多个用户（用 | 分隔）
to_user: "zhangsan|lisi"

# 推送给所有用户
to_user: "@all"
```

### 4. 启用消息加密

1. 在企业微信管理后台配置 Token 和 EncodingAESKey
2. 在 `config/wecom.yaml` 中填写相同的值：
   ```yaml
   token: "your_token_here"
   encoding_aes_key: "your_encoding_aes_key_here"
   ```
3. 重启应用

---

## 🐛 常见问题

### 1. 回调 URL 验证失败

**原因**：
- URL 无法访问
- 服务器防火墙阻止了请求
- 域名未备案

**解决方法**：
- 检查服务器是否正常运行
- 检查防火墙设置，开放 8000 端口（或您使用的端口）
- 确保域名已备案

### 2. 消息发送失败

**原因**：
- corp_id、corp_secret、agent_id 配置错误
- access_token 获取失败
- 网络问题

**解决方法**：
- 检查配置文件中的信息是否正确
- 查看日志输出，确认错误原因
- 检查网络连接

### 3. 收不到早安推送

**原因**：
- enabled 设置为 false
- 定时任务未启动
- 企业微信未启用

**解决方法**：
- 检查 `config/wecom.yaml` 中的 enabled 是否为 true
- 检查 `scheduler/cron_config.yaml` 中的 enabled 是否为 true
- 查看日志，确认定时任务是否执行

### 4. XML 解析失败

**原因**：
- 企业微信推送的消息格式不正确
- 消息体被修改

**解决方法**：
- 查看日志，确认收到的 XML 内容
- 检查是否有中间件修改了请求体

---

## 📊 监控和日志

### 1. 查看日志

应用运行时会在控制台输出日志：

```
[WeComNotifier] 成功获取 access_token，有效期 7200 秒
[WeComNotifier] 消息发送成功
[wecom_bot] 收到消息: 你好
[CronScheduler] 开始执行企业微信早安推送...
[CronScheduler] 企业微信消息发送成功
```

### 2. 监控指标

建议监控以下指标：
- 消息接收量（每分钟）
- 消息发送量（每分钟）
- API 调用成功率
- 响应时间

---

## 🔐 安全建议

1. **保护敏感信息**
   - 不要将 `corp_secret` 提交到代码仓库
   - 使用环境变量或密钥管理服务存储敏感信息

2. **使用 HTTPS**
   - 回调 URL 必须使用 HTTPS
   - 确保证书有效

3. **启用消息加密**
   - 在生产环境中建议启用消息加密
   - 防止消息被篡改和窃听

4. **限制访问权限**
   - 在企业微信管理后台设置应用的可见范围
   - 只允许必要的成员使用应用

---

## 📞 获取帮助

如果遇到问题，可以：

1. 查看日志输出
2. 运行测试脚本：`python test_wecom_integration.py`
3. 查看企业微信官方文档：https://developer.work.weixin.qq.com/document/
4. 查看实施总结文档：`WECOM_IMPLEMENTATION_SUMMARY.md`

---

## 🎉 完成！

恭喜！您已成功配置企业微信接入功能。现在可以：

- ✅ 在企业微信中发送消息给 AI Life OS
- ✅ 接收 AI Life OS 的回复
- ✅ 每天早上自动接收早安推送

开始享受智能化的生活管理体验吧！🚀
