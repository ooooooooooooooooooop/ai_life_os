---
name: guardian-retrospective
description: Guardian 复盘分析,检测偏差信号和行为模式
enabled: true
requires:
  config: []
---

# Guardian 复盘分析

## 任务

分析用户的历史行为事件,识别偏差信号和重复模式。

## 输入

```
事件日志:
{event_log}

当前状态:
{current_state}

目标状态:
{goal_state}
```

## 分析要求

1. **偏差检测**：识别实际行为与目标状态的偏离
2. **时间模式**：识别每日/每周固定时间执行的行为
3. **任务成功率**：统计各类任务的完成率
4. **最佳执行时段**：分析任务成功率最高的时间段

## 输出格式

```json
{
  "deviation_signals": [
    {
      "type": "偏差类型",
      "description": "偏差描述",
      "severity": "low|medium|high",
      "recommendation": "纠正建议"
    }
  ],
  "detected_patterns": [
    {
      "pattern": "描述行为模式",
      "frequency": "daily|weekly|monthly",
      "preferred_time": "HH:MM-HH:MM",
      "success_rate": 0.85,
      "confidence": 0.9
    }
  ],
  "insights": [
    "基于数据的洞察"
  ],
  "recommendations": [
    "基于分析的行动建议"
  ]
}
```

## 注意

- confidence < 0.5 的模式不输出
- 仅报告有足够样本（>= 3 次）的模式
- 偏差信号需要明确的时间或行为证据
