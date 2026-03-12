---
name: intent-recognition
description: 意图识别,理解用户输入的真实意图和上下文
enabled: true
requires:
  config: []
---

# Intent Recognition - 意图识别

## 任务

分析用户输入,识别其真实意图和上下文需求。

## 输入

```
用户输入: {user_input}
当前状态: {current_state}
历史上下文: {context}
```

## 识别维度

1. **显性意图**：用户明确表达的需求
2. **隐性意图**：用户未明说但实际需要的内容
3. **情绪状态**：用户的情绪倾向和压力水平
4. **时间紧迫性**：需求的紧急程度
5. **执行能力**：用户当前的执行能力评估

## 输出格式

```json
{
  "primary_intent": {
    "type": "goal_setting|task_management|information_query|status_update|help_request",
    "description": "主要意图描述",
    "confidence": 0.95
  },
  "secondary_intents": [
    {
      "type": "意图类型",
      "description": "次要意图描述",
      "confidence": 0.7
    }
  ],
  "emotional_state": {
    "valence": "positive|neutral|negative",
    "arousal": "high|medium|low",
    "stress_level": 0.3
  },
  "urgency": {
    "level": "high|medium|low",
    "deadline": "具体时间或null"
  },
  "execution_capacity": {
    "energy_level": 0.7,
    "focus_level": 0.8,
    "available_time": "2h"
  },
  "suggested_actions": [
    "基于意图识别的建议行动"
  ]
}
```

## 注意事项

- 优先识别显性意图
- 隐性意图需要充分证据支持
- 情绪状态评估要谨慎
- 考虑上下文连贯性
