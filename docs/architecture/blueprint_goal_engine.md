# Blueprint Goal Engine (目标驱动内核)

> **定位**: Guardian 的上层驱动器，将 Blueprint 长期目标转化为系统主动推进力
> 
> **核心原则**: 无硬编码目标，系统从用户 Blueprint 动态理解

---

## 1. 设计哲学

```text
Guardian = 约束引擎 (Constraint Engine) → 防止变坏
Goal Engine = 目标引擎 (Objective Engine) → 驱动变好

Guardian 服务于 Goal Engine，而非独立运作。
```

---

## 2. 三维目标框架（仅作为理解模型）

系统理解目标时使用的三个维度，但**不预设具体目标**：

| 维度 | 本质 | 典型关注点（举例，非硬编码） |
|------|------|---------------------------|
| **Wisdom** | 认知深度 | 思想连接、知识积累、创作产出 |
| **Experience** | 体验强度 | 心流状态、感官在场、深度投入 |
| **Connection** | 连接质量 | 深度对话、有意义的关系、利他行为 |

系统通过**阅读用户的 Blueprint 文档**来理解用户在每个维度下的具体期望。

---

## 3. 目标类型（作为理解模式）

系统识别目标时使用的四种模式：

```python
class GoalPattern(Enum):
    """目标模式，用于理解而非硬编码"""
    
    GROWTH = "growth"       # 需要持续增长的 (如: 知识、技能)
    FREQUENCY = "frequency" # 需要保持频率的 (如: 某种行为)
    DURATION = "duration"   # 需要保持时长的 (如: 专注时间)
    MILESTONE = "milestone" # 需要达成阶段的 (如: 项目交付)
```

---

## 4. 动态目标理解

### 4.1 从 Blueprint 提取目标

```python
class GoalExtractor:
    """从用户 Blueprint 文档动态提取目标"""
    
    def extract(self, blueprint_path: str) -> List[Goal]:
        """
        读取用户的 Blueprint 文档，
        使用 LLM 理解用户的长期目标，
        不硬编码任何具体目标
        """
        blueprint_content = Path(blueprint_path).read_text()
        
        # LLM 理解用户意图
        goals = self.llm.extract_goals(
            content=blueprint_content,
            dimensions=["wisdom", "experience", "connection"],
            patterns=["growth", "frequency", "duration", "milestone"]
        )
        
        return goals
```

### 4.2 自适应进度追踪

```python
class AdaptiveProgressTracker:
    """自适应追踪，不预设具体指标"""
    
    def assess(self, goal: Goal, context: Context) -> ProgressAssessment:
        """
        根据目标类型和上下文，
        动态判断进度状态
        """
        # 使用 LLM 评估当前状态 vs 目标预期
        assessment = self.llm.assess_progress(
            goal=goal,
            recent_activities=context.recent_activities,
            time_since_last_progress=context.time_delta
        )
        
        return assessment
```

---

## 5. "不安"机制（自适应）

```python
class AdaptiveAnxiety:
    """自适应不安触发，不硬编码阈值"""
    
    def check(self, goal: Goal, progress: ProgressAssessment) -> Alert:
        """
        根据目标的自然节奏判断是否应该"不安"
        
        例如：
        - 日常习惯类：连续缺失几天后不安
        - 大型项目类：长期停滞后不安
        - 关系类：疏远信号出现后不安
        
        具体阈值由 LLM 根据目标性质动态判断
        """
        should_be_anxious = self.llm.should_trigger_anxiety(
            goal=goal,
            progress=progress,
            goal_nature=self._infer_nature(goal)
        )
        
        if should_be_anxious:
            return Alert(
                level="GOAL_ANXIETY",
                representing="BLUEPRINT_SELF",
                message=self.llm.generate_anxiety_message(goal)
            )
        
        return Alert.OK
```

---

## 6. 与 Guardian 的集成

```python
class GoalDrivenGuardian:
    """目标驱动的 Guardian"""
    
    def __init__(self, blueprint_path: str):
        self.blueprint_path = blueprint_path
        self.goal_extractor = GoalExtractor()
        self.guardian = Guardian()
    
    def refresh_understanding(self):
        """重新理解 Blueprint（用户可能更新了）"""
        self.goals = self.goal_extractor.extract(self.blueprint_path)
    
    def daily_check(self) -> DailyInsight:
        """每日检查：哪些目标需要关注"""
        insights = []
        
        for goal in self.goals:
            progress = self.tracker.assess(goal, self.context)
            anxiety = self.anxiety.check(goal, progress)
            
            if anxiety:
                insights.append(anxiety)
        
        return DailyInsight(
            goals_on_track=[g for g in self.goals if self._is_on_track(g)],
            goals_needing_attention=[g for g in self.goals if not self._is_on_track(g)],
            anxieties=insights
        )
    
    def intervene(self, situation: Situation) -> Action:
        """干预时，说明是为哪个目标服务"""
        relevant_goal = self._find_relevant_goal(situation)
        
        return Action(
            type="INTERVENE",
            representing="BLUEPRINT_SELF",
            serving_goal=relevant_goal.description if relevant_goal else None
        )
```

---

## 7. Leisure 阶段行为

```python
def get_current_mode(self, phase: str) -> EngineMode:
    if phase == "leisure":
        return EngineMode.DORMANT  # 目标引擎休眠
    return EngineMode.ACTIVE
```

Leisure 阶段：
- ❌ Goal Engine 休眠，不推进目标
- ✅ Guardian 仍保护"不被 L1 琐事打扰"
- ✅ 让情感和审美主导

---

## 8. 核心原则

```text
1. 无硬编码目标
   - 所有目标从用户 Blueprint 动态提取
   - 用户更新 Blueprint，系统自动理解

2. 三维框架仅作理解模型
   - Wisdom / Experience / Connection
   - 帮助系统分类理解，不限制用户表达

3. 自适应判断
   - 进度追踪由 LLM 根据目标性质动态评估
   - 不安阈值由目标自然节奏决定

4. Guardian 服务于目标
   - Goal Engine 确定"应该推进什么"
   - Guardian 确保"能够推进"
```

---

## 9. 举例说明（非硬编码）Q

假设用户在 Blueprint 中写道：

> "我想每年出版一本关于'人类境况'的深度著作"

系统理解为：
- 维度：Wisdom
- 模式：Milestone
- 自然节奏：季度检查

假设用户写道：

> "确保每天有 4 小时进入'心流'状态"

系统理解为：
- 维度：Experience  
- 模式：Duration
- 自然节奏：每日检查

**但这些都是从用户文档动态提取的，系统不预设任何具体目标。**
