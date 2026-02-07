# Blueprint Anchor Layer (蓝图锚点层)

> **定位**: 对 Blueprint 的"冷静期结构化快照"
> 
> **核心原则**: 不是新权力，不是新智能，只是"冻结清醒意志"

---

## 1. 为什么需要 Anchor Layer

### 当前隐患

```text
Blueprint.md (自然语言)
    ↓
LLM 即时理解（每次都重新解析）
    ↓
Guardian 行动
```

问题不是"AI 夺权"，而是：

> **系统无法证明：今天的判断 ≈ 一个月前清醒时的你**

LLM 每次解析可能有微妙偏移，长期累积导致 **解释漂移 (Interpretation Drift)**。

### 解决方案

```text
Blueprint.md (自然语言)
    ↓
BlueprintAnchor (结构化快照，只读)
    ↓
Guardian 基于 Anchor 行动
```

---

## 2. BlueprintAnchor 结构

```python
from dataclasses import dataclass
from datetime import datetime
from typing import List

@dataclass(frozen=True)  # 不可变
class BlueprintAnchor:
    """
    Blueprint 的结构化快照
    - 只在用户清醒、主动确认时更新
    - 日常运行中只读，不生成、不推理
    """
    
    # 元信息
    version: str
    created_at: datetime
    confirmed_by_user: bool  # 必须为 True
    
    # 不可谈判的底线 (Guardian 必须保护)
    non_negotiables: List[str]
    # 例如：
    # - "L2 时间块神圣不可侵犯"
    # - "绝不多任务处理"
    
    # 长期承诺 (Goal Engine 追踪)
    long_horizon_commitments: List[str]
    # 例如：
    # - "认知资产持续增长"
    # - "深度关系保持活跃"
    
    # 反价值 (明确"不想成为的状态")
    anti_values: List[str]
    # 例如：
    # - "被碎片化信息淹没"
    # - "社交流于表面"
    
    # 本能劫持模式 (Guardian 识别并对抗)
    instinct_adversaries: List[str]
    # 例如：
    # - "无意识打开社交媒体"
    # - "L2 时间段内切换到娱乐应用"
```

---

## 3. 更新机制

### 3.1 只在清醒时更新

```python
class AnchorManager:
    """管理 Anchor 的生命周期"""
    
    def request_update(self) -> UpdateSession:
        """用户请求更新 Anchor"""
        return UpdateSession(
            prompt="请确认你现在处于清醒、理性的状态，而非疲劳或情绪化",
            requires_explicit_confirmation=True
        )
    
    def generate_anchor(self, blueprint_path: str) -> BlueprintAnchor:
        """从 Blueprint 生成新 Anchor"""
        content = Path(blueprint_path).read_text()
        
        # LLM 提取结构化信息
        extracted = self.llm.extract_anchor_fields(content)
        
        return BlueprintAnchor(
            version=self._next_version(),
            created_at=datetime.now(),
            confirmed_by_user=False,  # 待确认
            **extracted
        )
    
    def confirm_anchor(self, anchor: BlueprintAnchor, user_confirmation: bool) -> BlueprintAnchor:
        """用户确认后冻结"""
        if not user_confirmation:
            raise ValueError("Anchor requires explicit user confirmation")
        
        # 返回已确认的不可变版本
        return dataclasses.replace(anchor, confirmed_by_user=True)
```

### 3.2 更新前生成 Diff

```python
def show_diff(self, old: BlueprintAnchor, new: BlueprintAnchor) -> Diff:
    """展示变更，供用户审阅"""
    return Diff(
        added_non_negotiables=set(new.non_negotiables) - set(old.non_negotiables),
        removed_non_negotiables=set(old.non_negotiables) - set(new.non_negotiables),
        # ... 其他字段
    )
```

---

## 4. 运行时使用

### 4.1 Guardian 基于 Anchor 决策

```python
class AnchorAwareGuardian:
    """基于 Anchor 的 Guardian"""
    
    def __init__(self, anchor: BlueprintAnchor):
        self.anchor = anchor  # 只读引用
    
    def is_instinct_hijack(self, behavior: Behavior) -> bool:
        """检查是否匹配已知的本能劫持模式"""
        for pattern in self.anchor.instinct_adversaries:
            if self._matches(behavior, pattern):
                return True
        return False
    
    def is_violating_non_negotiable(self, action: Action) -> bool:
        """检查是否违反不可谈判底线"""
        for non_neg in self.anchor.non_negotiables:
            if self._conflicts(action, non_neg):
                return True
        return False
    
    def intervene(self, situation: Situation) -> Action:
        # 干预时引用 Anchor 作为依据
        if self.is_instinct_hijack(situation.behavior):
            return Action(
                type="INTERVENE",
                representing="BLUEPRINT_SELF",
                anchor_reference=self._find_matching_adversary(situation),
                message="这与你清醒时定义的本能劫持模式匹配"
            )
```

### 4.2 Goal Engine 基于 Anchor 追踪

```python
class AnchorAwareGoalEngine:
    """基于 Anchor 的目标引擎"""
    
    def __init__(self, anchor: BlueprintAnchor):
        self.anchor = anchor
    
    def get_commitments(self) -> List[str]:
        """获取长期承诺用于追踪"""
        return self.anchor.long_horizon_commitments
    
    def check_anti_value_drift(self, current_state: State) -> Alert:
        """检查是否在滑向反价值"""
        for anti_value in self.anchor.anti_values:
            if self._is_drifting_towards(current_state, anti_value):
                return Alert(
                    level="ANTI_VALUE_DRIFT",
                    message=f"你可能在滑向你明确反对的状态：{anti_value}"
                )
        return Alert.OK
```

---

## 5. 存储位置

```text
data/
└── anchors/
    ├── current.json          # 当前生效的 Anchor
    └── history/
        ├── v1_2026-01-15.json
        ├── v2_2026-02-01.json
        └── ...
```

---

## 6. 核心原则

```text
1. 不可变性 (Immutability)
   - Anchor 一旦确认，运行时不可修改
   - 更新必须生成新版本

2. 只读引用 (Read-Only Reference)
   - Guardian 和 Goal Engine 只读取 Anchor
   - 不推理、不生成、不修改

3. 清醒确认 (Sober Confirmation)
   - 只在用户清醒时更新
   - 需要显式确认

4. 可审计性 (Auditability)
   - 历史版本保留
   - 可追溯、可对比
   - 决策可引用具体 Anchor 条目
```

---

## 7. 与系统的关系

```text
┌─────────────────────────────────────────────────┐
│              Blueprint.md (自然语言)              │
│              用户的完整愿景和叙事                 │
└─────────────────────────────────────────────────┘
                        ↓ 提取
┌─────────────────────────────────────────────────┐
│           BlueprintAnchor (结构化快照)            │
│              冻结的清醒意志，只读                 │
└─────────────────────────────────────────────────┘
            ↓                         ↓
    ┌───────────────┐         ┌───────────────┐
    │  Goal Engine  │         │   Guardian    │
    │  追踪长期承诺  │         │  执行干预     │
    └───────────────┘         └───────────────┘
```

Anchor 是 Blueprint 和执行层之间的**可审计桥梁**。
