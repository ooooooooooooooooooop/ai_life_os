# 企业微信机器人快速启动指南

## 🚀 快速开始（3步完成）

### 第1步：运行配置脚本

```bash
python scripts/setup_wecom.py
```

按照提示输入企业微信应用信息：
- 企业ID (corp_id)
- 应用Secret (corp_secret)
- 应用AgentId (agent_id)

### 第2步：配置回调URL

在企业微信管理后台：
1. 进入应用详情页
2. 找到"设置API接收"
3. 填写URL：`http://69.63.211.116:8000/wecom/webhook`
4. 点击保存

### 第3步：重启服务

```bash
# 停止当前服务 (Ctrl+C)
# 重新启动
python main.py
```

## ✅ 验证配置

### 方法1：运行测试脚本

```bash
python test_wecom_integration.py
```

### 方法2：在企业微信中测试

1. 打开企业微信App
2. 找到"AI Life OS"应用
3. 发送消息："今天"
4. 应该收到回复

## 📋 当前状态

✅ **已完成：**
- 企业微信Bot框架已集成
- Webhook端点已配置：`/wecom/webhook`
- 消息接收和回复功能已实现
- 主动推送功能已实现
- 所有测试通过 (5/5)

⏳ **待配置：**
- 企业微信应用凭证 (corp_id, corp_secret, agent_id)
- 回调URL验证
- 启用配置 (enabled: true)

## 🔧 手动配置（可选）

如果不想使用配置脚本，可以手动编辑 `config/wecom.yaml`：

```yaml
corp_id: "你的企业ID"
corp_secret: "你的应用Secret"
agent_id: "你的应用AgentId"
to_user: "@all"
enabled: true
```

## 📚 详细文档

完整配置说明请参考：`docs/wecom_setup_guide.md`

## 🆘 常见问题

### Q: URL验证失败怎么办？

A: 检查服务是否正常运行：
```bash
curl http://69.63.211.116:8000/health
```

### Q: 消息无响应怎么办？

A: 检查配置是否正确：
```bash
cat config/wecom.yaml
```

### Q: 如何测试推送功能？

A: 运行配置脚本时会自动测试，或手动测试：
```python
from interface.notifiers.wecom_notifier import WeComNotifier
notifier = WeComNotifier()
notifier.send_raw("测试消息")
```

## 🎯 下一步

配置完成后，你可以：

1. **自定义消息处理**
   - 编辑 `interface/wecom_bot.py`
   - 添加更多指令处理逻辑

2. **集成AI功能**
   - 连接LLM实现智能对话
   - 实现任务管理、日程提醒等

3. **设置定时推送**
   - 配置早安问候
   - 定时任务提醒

## 📞 技术支持

遇到问题？查看：
- 详细文档：`docs/wecom_setup_guide.md`
- 测试脚本：`test_wecom_integration.py`
- 日志文件：`logs/`
