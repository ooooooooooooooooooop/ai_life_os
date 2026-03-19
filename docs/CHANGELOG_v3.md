# AI Life OS v3.x 变更日志

## v3.1 Guardian Optimization（本次优化）

### 新增模块
- `core/intervention_tracker.py` — 干预抵抗计数持久化
- `core/event_archiver.py` — 事件日志归档机制
- `config/persona/AGENTS.md` — Guardian 工作手册

### 核心改动
- `core/persona_loader.py` — Blueprint 接入 + AGENTS 注入
- `core/mood_detector.py` — 补充英文情绪关键词
- `core/conversation_summarizer.py` — mood 参数写入事件
- `core/interaction_handler.py` — 情绪感知 + acceptance 闭环
- `core/signal_detector.py` — 信号触发写入 intervention_level
- `core/llm_adapter.py` — TASK_PROFILE_MAP + task_type 路由
- 7个调用方 — 传入正确的 task_type
- `web/client/src/pages/Home.jsx` — SSE 实时推送 + isLive 指示器

### 测试
- `tests/test_new_modules.py` — 12个测试覆盖所有新增模块（12/12通过）

### 系统闭环
```
Blueprint → persona_loader → Guardian prompt
信号检测 → intervention_tracker → intervention_level
用户完成 → record_acceptance → 计数归零
对话 → mood_detector → 事件日志
事件 → SSE → 前端实时刷新
任务类型 → TASK_PROFILE_MAP → 对应模型
```

### 详细变更

#### Task #1: Blueprint 接入 Guardian 决策
- `persona_loader.py` 新增 `get_blueprint_anchor()` 函数
- Blueprint 摘要作为最高优先级注入 Guardian system prompt

#### Task #2: AGENTS.md 真正被读取
- `persona_loader.py` 新增 `agents` 字段
- AGENTS 内容追加到 system prompt 末尾

#### Task #3: 情绪数据接入事件日志
- `interaction_handler.py` 调用 `detect_mood()` 检测情绪
- `conversation_summarizer.py` 接收 mood 参数写入事件

#### Task #4: 干预抵抗计数持久化
- 新建 `core/intervention_tracker.py`
- 状态保存到 `data/intervention_state.json`
- 三级升级规则：gentle_nudge → firm_reminder → periodic_check

#### Task #5: intervention_tracker 接入实际干预流程
- `signal_detector.py` 调用 `record_resistance()` 记录抵抗
- `interaction_handler.py` 调用 `record_acceptance()` 重置计数

#### Task #6: 事件日志归档机制
- 新建 `core/event_archiver.py`
- 自动归档超龄事件到 `data/archive/events_YYYY-MM.jsonl`
- 丢弃 1970 年脏数据

#### Task #7: 前端接入 Guardian 实时推送
- `Home.jsx` 新增 SSE 连接 `/api/v1/events`
- 监听 7 种事件类型触发 `fetchAll()`
- 绿色圆点指示器显示连接状态

#### Task #8: 为新增模块补充测试
- 新建 `tests/test_new_modules.py`
- 覆盖 intervention_tracker、event_archiver、persona_loader、mood_detector

#### Task #9: 多模型路由实现
- `llm_adapter.py` 新增 `TASK_PROFILE_MAP` 映射
- `get_llm()` 新增 `task_type` 参数
- 7 个调用方传入正确的 task_type

#### Task #10: 文档更新
- 更新 `README_zh.md` 核心特性列表
- 新建 `docs/CHANGELOG_v3.md` 变更日志
