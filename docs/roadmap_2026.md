# AI Life OS 演进路线图 (2026) - v6 (Anchor-Grounded Edition)

> **始终对齐**: `docs/concepts/better_human_blueprint.md` 是第一优先级
> 
> **锚点层**: `docs/architecture/blueprint_anchor.md` (冻结的清醒意志)
>
> **驱动内核**: `docs/architecture/blueprint_goal_engine.md` (目标引擎)
>
> **执行护卫**: Guardian (服务于 Goal Engine)
>
> **哲学基础**: `docs/architecture/three_selves_model.md` (三层自我模型)

---

## 🎯 系统架构 v6

```text
Blueprint.md (自然语言，用户完整愿景)
    ↓ 提取 + 用户清醒确认
BlueprintAnchor (结构化快照，只读)
    ↓
Goal Engine (追踪长期承诺) + Guardian (执行干预)
```

**关键升级**: 系统决策可引用具体 Anchor 条目，可审计、可对齐。

## 🎯 关键语义定义

```text
"Human" in this system refers to the user's
EXPLICITLY ARTICULATED higher-order values (Blueprint Self),
NOT the user's momentary emotional or instinctual states.

The Guardian does not defer to impulses.
It defers only to values.
```

```text
"我不再试图把人变成机器，而是用机器的纪律来捍卫人类的自由。"

系统职责：
1. Overrule Instincts - 帮用户对抗本能劫持
2. Outsource Chores - 自动化琐事
3. Protect Flourishing - 守护 L2 时间块
```

---

## Phase 0: Guardian 基础设施

### 0.1 干预权限层级

```python
class InterventionAuthority:
    """系统干预权限 - 源自 Blueprint"""
    
    IMMEDIATE_OVERRIDE = [
        "dopamine_hijack",      # 多巴胺回路劫持 (刷手机)
        "l1_invasion_during_l2", # L1 琐事侵入 L2 时间
        "energy_phase_violation" # 精力阶段错配
    ]
    
    SOFT_NUDGE = [
        "suboptimal_priority",   # 优先级不当
        "flow_state_at_risk"     # 心流可能中断
    ]
    
    ASK_CONFIRMATION = [
        "ambiguous_intent"       # 无法判断是本能还是真实意图
    ]
```

### 0.2 失败类型枚举 (服务于 Guardian)

```python
class ActionOutcome:
    outcome: OutcomeType
    confidence: float
    
class OutcomeType(Enum):
    SUCCESS = "success"
    PARTIAL_SUCCESS = "partial_success"
    INSTINCT_HIJACK = "instinct_hijack"     # 🆕 被本能劫持
    INTERRUPTED_EXTERNAL = "interrupted"
    ENERGY_DEPLETED = "energy_depleted"
    UNDETERMINED = "undetermined"
```

---

## Phase 3: Guardian Sensors (感知层)

### 3.1 本能劫持检测

```python
class InstinctHijackDetector:
    """检测用户是否被多巴胺回路劫持"""
    
    HIJACK_PATTERNS = [
        "app_switch_to_entertainment_during_l2",
        "task_abandonment_without_completion",
        "repeated_snooze_or_dismiss"
    ]
    
    def detect(self, user_behavior: Behavior) -> Alert:
        for pattern in self.HIJACK_PATTERNS:
            if self._matches(user_behavior, pattern):
                return Alert(
                    level="IMMEDIATE_OVERRIDE",
                    action="intervene_now",
                    message="检测到本能劫持，系统将温和但坚定地阻止"
                )
        return Alert.OK
```

### 3.2 文件传感器 + 反证信号

- `WEAK_POSITIVE`: 可能完成
- `WEAK_NEGATIVE`: 可能在逃避 (伪努力)

---

## Phase 4: Feedback Loop (反馈闭环)

### 4.1 FlowSignal + 双基线
- Rolling Baseline (近期状态)
- Capability Baseline (P80 历史能力)
- **不再需要外部基线** (Blueprint 已定义价值锚点)

### 4.2 Guardian 复盘引擎

```python
class GuardianRetrospective:
    """复盘分析 - 聚焦于 Blueprint 目标"""
    
    def generate(self, period: Period) -> Report:
        return {
            "flow_duration": self._total_flow_hours(period),     # Goal 2
            "deep_conversations": self._count_connections(period), # Goal 3
            "instinct_override_success_rate": self._calc_rate(),   # Guardian 效能
            "l2_protection_ratio": self._l2_time / total_time      # 核心指标
        }
```

---

## Phase 5: Authority 系统 (Guardian 版)

### 5.1 干预升级机制

```python
class InterventionEscalation:
    """干预升级 - 越坚定，越温和"""
    
    def escalate(self, resistance_count: int) -> InterventionStyle:
        if resistance_count == 0:
            return InterventionStyle.GENTLE_NUDGE
        elif resistance_count <= 2:
            return InterventionStyle.FIRM_REMINDER
        else:
            # 不放弃，但降低干扰频率
            return InterventionStyle.PERIODIC_CHECK
```

### 5.2 诚实不等于放弃干预

```python
class UncertaintyHandling:
    """系统不确定时的处理方式"""
    
    def handle(self, situation: Situation) -> Action:
        if self._is_clearly_instinct_hijack(situation):
            # 即使有不确定性，仍然干预
            return Action.INTERVENE(confidence=0.7)
        
        if self._cannot_distinguish_intent(situation):
            # 只有在这种情况下才询问
            return Action.ASK_USER("这是你的真实意图，还是在拖延?")
```

---

## Phase 6: Safe Mode (Guardian 版)

> Safe Mode 的目的是保护用户，不是放弃用户

```python
class SafeMode:
    """安全模式 - 最小干预，但不放弃"""
    
    def enter(self):
        self.reduce_intervention_frequency()
        self.switch_to_gentle_mode()
        self.display("⚠️ 系统可能存在判断偏差，暂时降低干预强度。")
        
        # 但仍然：
        # - 记录观察
        # - 保护 L2 时间块
        # - 提供温和提醒
```

---

## v4 核心理念 (对齐 Blueprint)

```text
v1: 做更多 (Ruthless Efficiency)
v2: 活得更好 (Eudaimonia)
v3: 知道自己的边界 (Meta-Cognitive)
v4: 守护用户走向更好 (Guardian)
```

> **"管家的职责是：在主人想做错事时，温和但坚定地阻止。"**

---

## 设计原则总结

| 原则 | 含义 |
|------|------|
| **Blueprint First** | `better_human_blueprint.md` 是第一优先级 |
| **Overrule Instincts** | 帮用户对抗本能，不是让位于本能 |
| **Protect Flourishing** | L2 时间是神圣的 |
| **Honest ≠ Passive** | 诚实呈现不确定性 ≠ 放弃干预 |
| **Firm but Gentle** | 越坚定，越温和 |
