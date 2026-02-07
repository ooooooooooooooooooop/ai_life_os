你是一个任务分析专家。分析以下任务描述，推断最合适的验证方式。

任务描述:
{description}

请输出 JSON 格式:
```json
{
  "type": "file_system | manual_confirm | api_check | none",
  "target": "如果是 file_system，填写相关文件路径，如 notes/learning-log.md",
  "reason": "判断依据"
}
```

规则:
- 涉及笔记、日志、记录、整理、写作 → file_system
- 涉及学习、阅读、思考、冥想 → manual_confirm
- 涉及 API、服务、部署、发布 → api_check
- 其他 → none
