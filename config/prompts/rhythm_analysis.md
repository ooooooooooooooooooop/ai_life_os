# 习惯分析提示词

## 任务

分析用户的历史行为事件，识别重复模式和习惯。

## 输入

```
事件日志:
{event_log}

当前状态:
{current_state}
```

## 分析要求

1. **时间模式**：识别每日/每周固定时间执行的行为
2. **任务成功率**：统计各类任务的完成率
3. **最佳执行时段**：分析任务成功率最高的时间段

## 输出格式

```json
{
  "detected_habits": [
    {
      "pattern": "描述行为模式",
      "frequency": "daily|weekly|monthly",
      "preferred_time": "HH:MM-HH:MM",
      "success_rate": 0.85,
      "confidence": 0.9
    }
  ],
  "recommendations": [
    "基于习惯的行动建议"
  ]
}
```

## 注意

- confidence < 0.5 的模式不输出
- 仅报告有足够样本（>= 3 次）的模式
