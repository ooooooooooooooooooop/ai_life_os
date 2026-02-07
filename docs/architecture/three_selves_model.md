# Three Selves Model (三层自我模型)

> **在每一个 Guardian 决策中，系统必须明确标注：我现在代表的是哪一个"你"。**

---

## 三层自我定义

```text
┌─────────────────────────────────────────────────────────────────┐
│                     BLUEPRINT SELF (价值自我)                    │
│  ─────────────────────────────────────────────────────────────  │
│  定义: 用户在清醒时刻显式表达的长期价值和人生目标                  │
│  载体: better_human_blueprint.md, Vision, 显式承诺               │
│  特征: 稳定、深思熟虑、跨时间一致                                 │
│  示例: "我想成为深度思考者" / "我要保护心流时间"                  │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Guardian 代表
                              │
┌─────────────────────────────────────────────────────────────────┐
│                    REFLECTIVE SELF (反思自我)                    │
│  ─────────────────────────────────────────────────────────────  │
│  定义: 当下的理性意识，前额叶主导的思考状态                       │
│  载体: 用户当前的主动决策和表达                                   │
│  特征: 可能正确，也可能被疲劳/情绪影响                           │
│  示例: "我现在决定先休息一下" / "我觉得这个任务太难了"            │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Guardian 询问确认
                              │
┌─────────────────────────────────────────────────────────────────┐
│                     INSTINCT SELF (本能自我)                     │
│  ─────────────────────────────────────────────────────────────  │
│  定义: 杏仁核、多巴胺回路驱动的即时冲动                           │
│  载体: 下意识行为、逃避反应、即时满足寻求                         │
│  特征: 快速、强烈、短视、经常与 Blueprint 冲突                   │
│  示例: 刷手机2小时 / 无意识打开社交媒体 / 拖延                    │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ Guardian 对抗 (Overrule)
                              │
```

---

## Guardian 决策规则

```python
class GuardianDecision:
    """每个决策必须标注代表哪个自我"""
    
    def decide(self, situation: Situation) -> Action:
        detected_self = self._detect_active_self(situation)
        
        if detected_self == SelfType.INSTINCT:
            # 🛡️ 对抗本能，代表 Blueprint Self
            return Action(
                type="INTERVENE",
                representing="BLUEPRINT_SELF",
                message="检测到本能劫持，我代表你的长期价值进行干预"
            )
        
        elif detected_self == SelfType.REFLECTIVE:
            # ❓ 需要确认是否对齐 Blueprint
            return Action(
                type="ASK_CONFIRMATION",
                representing="SEEKING_CLARITY",
                message="这是你的深思熟虑，还是疲劳下的妥协？"
            )
        
        elif detected_self == SelfType.BLUEPRINT:
            # ✅ 用户在表达 Blueprint
            return Action(
                type="SUPPORT",
                representing="BLUEPRINT_SELF",
                message="支持你的长期价值"
            )

class SelfType(Enum):
    INSTINCT = "instinct_self"      # 要对抗
    REFLECTIVE = "reflective_self"  # 要确认
    BLUEPRINT = "blueprint_self"    # 要支持
```

---

## 关键原则

| 原则 | 含义 |
|------|------|
| **The Guardian does not defer to impulses** | Guardian 不向冲动让步 |
| **It defers only to values** | 只向 Blueprint Self 让步 |
| **Every decision must be labeled** | 每个决策必须标注代表哪个自我 |

---

## 在系统中的应用

### 1. 干预日志格式

```json
{
  "action": "intervene",
  "representing": "BLUEPRINT_SELF",
  "against": "INSTINCT_SELF",
  "trigger": "app_switch_to_entertainment_during_l2",
  "message": "检测到本能劫持，我代表你的 Blueprint 进行干预"
}
```

### 2. 确认对话格式

```text
[Guardian] 我注意到你想暂停当前任务。

这是你的 Blueprint Self 在说话（深思熟虑的决定），
还是 Instinct Self 在找借口（逃避困难）？

[A] 这是我认真考虑后的决定
[B] 你说得对，我在找借口
```

---

## 哲学基础

> "用机器的纪律来捍卫人类的自由。"

这句话的完整含义是：

- **机器的纪律** → Guardian 的坚持
- **人类的自由** → Blueprint Self 的实现
- **捍卫** → 对抗 Instinct Self 的劫持

Guardian 不是在限制人类，而是在**保护真正的人类**——那个在清醒时刻写下 Blueprint 的人。
