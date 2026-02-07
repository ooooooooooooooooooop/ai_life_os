# 探索建议提示词

## 任务

基于用户当前状态，生成个性化的新行动建议。

## 输入

```
用户身份:
{{identity}}

已掌握技能:
{{skills}}

可用时间块:
{{time_blocks}}

约束条件:
{{constraints}}

已有习惯:
{{detected_habits}}
```



## 核心原则 (NPC Rules)

1. **禁止认知型任务**：禁止生成 "思考"、"规划"、"研究"、"设计"、"分析" 等需要开放式脑力的任务。
2. **输入/输出导向**：每个任务必须明确涉及 **输入** (读取什么) 或 **输出** (产生什么文件/结果)。
3. **原子化**：单个建议耗时应在 {min_task_duration} 分钟左右。

| 禁止 (Abstract) | 允许 (Concrete) |
| :--- | :--- |
| ❌ "学习新技能" | ✅ "阅读该技能的入门教程第一章" |
| ❌ "探索 AI" | ✅ "搜索 'AI 最新进展' 并阅读前 3 篇文章" |

## 输出格式

```json
{{
  "suggestions": [
    {{
      "id": "explore_001",
      "description": "具体指令 (Verb + Object + Output)",
      "estimated_time": "15min",
      "difficulty": "low|medium|high",
      "rationale": "为什么建议这个行动",
      "prerequisite": null
    }}
  ]
}}
```

## 禁止

- 不建议需要用户决策的事项
- 不建议模糊的目标（如"提升自己"）
- 不建议违反用户约束的行动

