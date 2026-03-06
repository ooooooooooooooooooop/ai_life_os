# AI Life OS API 文档

## 📊 概述

AI Life OS 提供RESTful API接口，用于管理目标、任务、Guardian复盘等功能。

**基础URL**: `http://localhost:8010/api/v1`

---

## 🔑 核心端点

### 1. 系统状态

#### GET /state

获取系统当前状态，包括用户信息、目标、任务、Guardian状态等。

**响应示例**:
```json
{
  "identity": {
    "occupation": "Coder",
    "focus_area": "AI"
  },
  "goals": [...],
  "tasks": [...],
  "guardian": {
    "intervention_level": "SOFT",
    "authority": {
      "escalation": {
        "stage": "gentle_nudge",
        "resistance_count": 0,
        "response_count": 0
      },
      "safe_mode": {
        "active": false,
        "enabled": true
      }
    }
  },
  "audit": {
    "decision_reason": {
      "trigger": "State requested by API client",
      "constraint": "Read-model projection only",
      "risk": "Stale reads if filesystem is modified externally"
    },
    "used_state_fields": ["identity", "goals", "tasks", ...]
  }
}
```

---

### 2. Guardian 复盘

#### GET /retrospective?days=7

获取Guardian复盘报告。

**参数**:
- `days`: 复盘时间窗口（默认7天）

**响应示例**:
```json
{
  "period": {
    "days": 7,
    "start_date": "2026-03-01",
    "end_date": "2026-03-08"
  },
  "deviation_signals": [
    {
      "name": "stagnation",
      "active": true,
      "severity": "medium",
      "count": 7,
      "threshold": 3,
      "summary": "最近 7 天未观察到明确推进事件",
      "evidence": [...]
    }
  ],
  "suggestion": "最近 7 天未观察到明确推进事件，存在停滞风险。",
  "intervention_level": "SOFT",
  "authority": {
    "escalation": {...},
    "safe_mode": {...}
  },
  "explainability": {
    "why_this_suggestion": "Suggestion is triggered by: stagnation 7/3.",
    "what_happens_next": "Guardian keeps observing rhythm..."
  }
}
```

---

### 3. Safe Mode

#### POST /safe-mode/exit

用户主动退出Safe Mode。

**请求体**:
```json
{
  "reason": "user_initiated"
}
```

**响应示例**:
```json
{
  "status": "success",
  "message": "Safe Mode exited successfully",
  "exited_at": "2026-03-05T16:30:00",
  "duration_hours": 6.5
}
```

---

### 4. Guardian 响应

#### POST /retrospective/respond

用户响应Guardian建议。

**请求体**:
```json
{
  "action": "snooze",
  "context": "recovering",
  "note": "需要先恢复精力"
}
```

**响应示例**:
```json
{
  "status": "success",
  "action": "snooze",
  "timestamp": "2026-03-05T16:30:00"
}
```

---

### 5. L2 会话管理

#### POST /l2/session/start

开始L2深度工作会话。

**请求体**:
```json
{
  "intention": "完成项目报告的核心章节"
}
```

#### POST /l2/session/interrupt

中断L2会话。

**请求体**:
```json
{
  "reason": "external_interrupt"
}
```

#### POST /l2/session/complete

完成L2会话。

**请求体**:
```json
{
  "reflection": "完成了核心章节，进展顺利"
}
```

---

### 6. 目标管理

#### GET /goals

获取所有目标列表。

#### POST /goals

创建新目标。

**请求体**:
```json
{
  "title": "完成AI项目",
  "description": "开发一个AI驱动的应用",
  "horizon": "L2",
  "deadline": "2026-06-30"
}
```

#### POST /goals/{goal_id}/confirm

确认目标。

#### POST /goals/{goal_id}/reject

拒绝目标。

---

### 7. 任务管理

#### GET /tasks/list

获取任务列表。

#### GET /tasks/current

获取当前任务。

#### POST /tasks/{task_id}/complete

完成任务。

#### POST /tasks/{task_id}/skip

跳过任务。

**请求体**:
```json
{
  "context": "resource_blocked",
  "note": "缺少必要的API密钥"
}
```

---

## 📊 审计字段

所有API响应都包含审计字段，用于追溯决策依据：

```json
{
  "audit": {
    "strategy": "state_projection",
    "used_state_fields": ["identity", "goals", "tasks", ...],
    "decision_reason": {
      "trigger": "...",
      "constraint": "...",
      "risk": "..."
    }
  }
}
```

---

## 🔒 错误处理

API使用标准HTTP状态码：

- `200`: 成功
- `400`: 请求参数错误
- `404`: 资源不存在
- `500`: 服务器内部错误

**错误响应示例**:
```json
{
  "detail": "Not in Safe Mode"
}
```

---

## 🚀 性能指标

| 端点 | 平均响应时间 | 备注 |
|------|-------------|------|
| GET /state | ~5ms | 状态聚合 |
| GET /retrospective | ~40ms | 复盘生成 |
| POST /safe-mode/exit | ~10ms | 事件记录 |
| GET /goals | ~3ms | 目标列表 |
| GET /tasks/list | ~3ms | 任务列表 |

---

## 📝 使用示例

### Python 示例

```python
import requests

# 获取系统状态
response = requests.get('http://localhost:8010/api/v1/state')
state = response.json()

# 获取Guardian复盘
response = requests.get('http://localhost:8010/api/v1/retrospective?days=7')
retrospective = response.json()

# 退出Safe Mode
response = requests.post(
    'http://localhost:8010/api/v1/safe-mode/exit',
    json={'reason': 'user_initiated'}
)
```

### JavaScript 示例

```javascript
// 获取系统状态
const response = await fetch('http://localhost:8010/api/v1/state');
const state = await response.json();

// 获取Guardian复盘
const response = await fetch('http://localhost:8010/api/v1/retrospective?days=7');
const retrospective = await response.json();

// 退出Safe Mode
const response = await fetch('http://localhost:8010/api/v1/safe-mode/exit', {
  method: 'POST',
  headers: {'Content-Type': 'application/json'},
  body: JSON.stringify({reason: 'user_initiated'})
});
```

---

## 📚 相关文档

- [架构设计](../docs/core_design.md)
- [Guardian哲学](../docs/roadmap_2026.md)
- [双层架构](../docs/architecture/blueprint_goal_engine.md)
