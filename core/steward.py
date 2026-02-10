"""
The Steward - AI Life OS Core Decision Engine.

Generates action plans with full audit trail:
- decision_reason (Trigger, Constraint, Risk)
- used_state_fields
- priority_level

Steward Role Upgrade (Design 2.0):
- Implements Dual-Layer Scheduling (Substrate vs Flourishing)
- Prioritizes "Big Rocks" (L2 Flow Sessions)
- Batches "Gravel" (L1 Chores)
"""
import json
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from core.bootstrap import is_cold_start, get_bootstrap_tasks
from core.llm_adapter import get_llm
from core.config_manager import config
from core.goal_decomposer import GoalType

import uuid
from core.utils import load_prompt, parse_llm_json
from core.objective_engine.registry import GoalRegistry
from core.objective_engine.models import GoalState, ObjectiveNode, GoalLayer, GoalSource
from core.strategic_engine.bhb_parser import parse_bhb
from core.rule_evaluator import RuleEvaluator


class DecisionReason:
    """Structured decision reason for auditability."""

    def __init__(
        self,
        trigger: str,
        constraint: str,
        risk: str
    ):
        self.trigger = trigger      # Why now?
        self.constraint = constraint  # Why not others?
        self.risk = risk            # What if it fails?

    def to_dict(self) -> Dict[str, str]:
        return {
            "trigger": self.trigger,
            "constraint": self.constraint,
            "risk": self.risk
        }


class Steward:
    """
    AI decision-making engine (The Steward).
    Formerly 'Planner'.

    Follows Dual-Layer strategies:
    1. Flourishing (L2): High priority, protected blocks.
    2. Substrate (L1): Batched, high efficiency.
    3. Maintenance (System): Essential repairs.
    """

    # Priority order updated for Eudaimonia
    PRIORITY_ORDER = ["maintenance", "flourishing_session", "substrate_task", "exploration"]

    def __init__(self, state: Dict[str, Any], registry: Optional[GoalRegistry] = None):
        self.state = state
        self.used_fields: List[str] = []
        self.registry = registry or GoalRegistry()
        self._rule_evaluator = RuleEvaluator()
        self._goal_engine = None
        self._anchor_manager = None

    def _record_field_usage(self, field_path: str) -> None:
        """Track which state fields were used in decision."""
        if field_path not in self.used_fields:
            self.used_fields.append(field_path)

    def _get_field(self, field_path: str) -> Any:
        """Get nested field and record usage."""
        self._record_field_usage(field_path)

        parts = field_path.split(".")
        value = self.state
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value

    def run_planning_cycle(self) -> Dict[str, Any]:
        """
        Run the full planning cycle:
        1. Check for cold start (bypass heavy LLM calls)
        2. Infer missing goals (L2) - only if not cold start
        3. Generate next actions (L1)
        4. Execute auto-maintenance tasks
        """
        # CRITICAL: Check cold start FIRST before any LLM calls
        # This prevents slow goal inference from blocking bootstrap flow
        if is_cold_start(self.state):
            plan = self._generate_bootstrap_plan()
            executed = self.execute_auto_actions(plan)
            if executed:
                plan["executed_auto_tasks"] = executed
                plan["actions"] = [
                    a for a in plan.get("actions", [])
                    if a.get("id") not in executed
                ]
            return plan

        # Only run goal inference when system is initialized
        self._infer_missing_goals()

        # Generate Plan (L1)
        plan = self.generate_plan()

        # Execute Auto-Actions
        executed = self.execute_auto_actions(plan)
        if executed:
            plan["executed_auto_tasks"] = executed
            # Filter out executed tasks from downstream visibility
            plan["actions"] = [
                a for a in plan.get("actions", [])
                if a["id"] not in executed
            ]

        return plan

    def generate_plan(self) -> Dict[str, Any]:
        """
        Generate decision plan with Allocator logic.
        """
        self.used_fields = []  # Reset tracking

        # Check for cold start first
        if is_cold_start(self.state):
            return self._generate_bootstrap_plan()

        # Check for failures
        failed_actions = self._handle_failures()

        # Generate actions
        actions = []
        actions.extend(self._generate_maintenance_actions())

        # [Steward Logic]
        # 1. Distribute Active Goals into L1 and L2
        l1_actions, l2_actions = self._generate_goal_actions()
        actions.extend(l1_actions)
        actions.extend(l2_actions)

        # 2. Add Habits (Rhythm)
        actions.extend(self._generate_rhythm_actions())

        # 3. Add Exploration (if capacity remains)
        if len(actions) < config.DAILY_TASK_LIMIT:
             actions.extend(self._generate_exploration_actions())

        # [Energy Phase Dispatching] (New Phase 8)
        current_phase = self._get_current_phase()
        actions = self._filter_actions_by_phase(current_phase, actions)

        # Sort by updated priority
        actions = self._sort_by_priority(actions)

        plan = {
            "generated_at": datetime.now().isoformat(),
            "energy_phase": current_phase,
            "actions": actions[:config.DAILY_TASK_LIMIT],
            "failed_action_handling": failed_actions,
            "audit": {
                "used_state_fields": self.used_fields,
                "strategy": f"Energy Phase ({current_phase}) Dispatching",
                "decision_reason": DecisionReason(
                    trigger=f"Daily Steward Cycle (Phase: {current_phase})",
                    constraint=f"Max {config.DAILY_TASK_LIMIT} items",
                    risk="Cognitive Overload if L1 leaks into L2"
                ).to_dict()
            }
        }

        return plan

    def get_current_phase(self) -> str:
        """Public accessor for current energy phase (used by UI)."""
        return self._get_current_phase()

    def _sort_by_priority(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort actions by priority (High to Low)."""
        priority_map = {
            "critical_maintenance": 0,
            "flourishing_session": 1,
            "deep_work": 1,
            "substrate_task": 2,
            "maintenance": 3
        }

        return sorted(
            actions,
            key=lambda x: priority_map.get(x.get("priority", "maintenance"), 99)
        )

    def _get_current_phase(self) -> str:
        """Determine current energy phase based on time."""
        now = datetime.now()
        current_time = now.strftime("%H:%M")

        for time_range, phase in config.ENERGY_PHASES.items():
            start_str, end_str = time_range.split("-")
            if start_str <= current_time < end_str:
                return phase

        return config.DEFAULT_ENERGY_PHASE  # 使用配置 fallback

    def _filter_actions_by_phase(
        self,
        phase: str,
        actions: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Filter actions using RuleEvaluator (Config-Driven with Hot Reload)."""
        return self._rule_evaluator.filter_actions(phase, actions)

    def _generate_bootstrap_plan(self) -> Dict[str, Any]:
        """Generate cold start bootstrap plan with smart filtering."""
        all_tasks = get_bootstrap_tasks(self.state)

        # Smart Filter: Only keep tasks for missing fields
        filtered_tasks = []
        for task in all_tasks:
            target_field = task.get("target_field")
            if target_field:
                current_val = self._get_field(target_field)
                # If value exists and is not empty/false, skip task
                if current_val:
                    continue
            filtered_tasks.append(task)

        # If no bootstrap tasks needed (e.g. only time missing), fallback to maintenance
        if not filtered_tasks:
            return {
                "generated_at": datetime.now().isoformat(),
                "actions": self._generate_maintenance_actions(),
                "is_bootstrap": False,
                "audit": {
                    "decision_reason": {
                        "trigger": "Check complete",
                        "constraint": "None",
                        "risk": "None",
                    }
                },
            }

        return {
            "generated_at": datetime.now().isoformat(),
            "actions": filtered_tasks,
            "is_bootstrap": True,
            "audit": {
                "used_state_fields": ["identity", "time_state"],
                "decision_reason": DecisionReason(
                    trigger="Cold start detected",
                    constraint="Bootstrap required",
                    risk="System unintialized"
                ).to_dict()
            }
        }

    def _handle_failures(self) -> List[Dict[str, Any]]:
        """Handle execution failures."""
        from core.failure_strategy import (
            FailureHandler, FailureContext
        )

        active_tasks = self._get_field("ongoing.active_tasks") or []
        handler = FailureHandler()
        results = []

        for task in active_tasks:
            if task.get("status") == "failed":
                legacy_type = task.get("failure_type", "unknown")
                failure_type = handler.classify_failure(legacy_type)

                context = FailureContext(
                    task_id=task.get("id", "unknown"),
                    failure_type=failure_type,
                    reason=task.get("failure_reason", "No reason provided"),
                    original_task=task,
                    failure_count=task.get("failure_count", 1)
                )

                result = handler.handle(context)
                results.append({
                    "original_task_id": result.task_id,
                    "action": result.action,
                    "reason": result.rationale,
                    "confidence": result.confidence,
                    "metadata": result.metadata
                })

        return results

    def execute_auto_actions(self, plan: Dict[str, Any]) -> List[str]:
        """Execute any auto=True actions in the plan."""
        executed = []
        actions = plan.get("actions", [])

        for action in actions:
            if action.get("auto", False):
                if action["id"] == "maint_time_sync":
                    # Execute Time Sync
                    from core.event_sourcing import append_event
                    append_event({
                        "type": "time_tick",
                        "timestamp": datetime.now().isoformat(),
                        "date": datetime.now().strftime("%Y-%m-%d"),
                        "time": datetime.now().strftime("%H:%M:%S")
                    })
                    executed.append(action["id"])

        return executed

    def _generate_maintenance_actions(self) -> List[Dict[str, Any]]:
        """System level maintenance."""
        actions = []
        time_state = self._get_field("time_state")
        if not time_state or not time_state.get("current_date"):
            actions.append({
                "id": "maint_time_sync",
                "description": "同步系统时间",
                "priority": "maintenance",
                "auto": True
            })
        return actions

    def _generate_goal_actions(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        [v6] Upgrade: Generate L1/L2 actions from Goal Engine & Legacy Registry.
        Now integrates Anchor filtering.
        """
        l1_actions = []
        l2_actions = []

        # [v6] 1. Goal Engine Integration
        if self._goal_engine:
            goals = self._goal_engine.get_goals()
            anxieties = self._goal_engine.check_all_anxieties()

            # Anxiety -> Critical Maintenance (L1)
            for alert in anxieties:
                l1_actions.append({
                    "id": f"anxiety_{str(uuid.uuid4())[:8]}",
                    "description": alert.message,
                    "priority": "critical_maintenance",
                    "verification": {"type": "manual_confirm"},
                    "source": "Goal Engine (Anxiety)"
                })

            # Goals -> Deep Work (L2)
            for goal in goals:
                l2_actions.append({
                    "id": f"goal_step_{goal.id}",
                    "description": f"推进目标 [{goal.dimension.value}]: {goal.title}",
                    "priority": "deep_work",
                    "verification": {"type": "manual_confirm"},
                    "source": "Goal Engine"
                })

        # 2. Legacy Registry Integration
        registry_l1, registry_l2 = self._process_registry_goals_legacy()
        l1_actions.extend(registry_l1)
        l2_actions.extend(registry_l2)

        # 3. Anchor Filtering
        l1_actions = self._filter_actions_by_anchor(l1_actions)
        l2_actions = self._filter_actions_by_anchor(l2_actions)

        return l1_actions, l2_actions

    def _filter_actions_by_anchor(self, actions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """基于 Anchor 过滤动作"""
        if not self._anchor_manager:
            return actions

        anchor = self._anchor_manager.get_current()
        if not anchor:
            return actions

        filtered = []
        for action in actions:
            if self._is_violating_anchor(action, anchor):
                print(f"[Guardian] Blocked action violating anchor: {action['description']}")
                continue
            filtered.append(action)
        return filtered

    def _is_violating_anchor(self, action: Dict[str, Any], anchor: Any) -> bool:
        """检查动作是否违反 Anchor"""
        desc = action.get("description", "").lower()
        for anti in anchor.anti_values:
            if anti.lower() in desc:
                return True
        return False

    def _process_registry_goals_legacy(self) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Original Registry Logic (Refactored)"""
        l1_actions = []
        l2_actions = []

        active_goals = [g for g in self.registry.goals if g.state == GoalState.ACTIVE]
        if not active_goals:
            # Fallback Logic
            inferred_actions = self._infer_missing_goals()
            if inferred_actions:
                 return [], inferred_actions
            return [], self._handle_idle_state()

        for objective_node in active_goals:
            from core.goal_decomposer import Goal, SubTask, get_next_actionable_task

            goal_type_str = objective_node.goal_type or GoalType.SUBSTRATE.value

            try:
                goal = Goal(
                    id=objective_node.id,
                    title=objective_node.title,
                    description=objective_node.description,
                    created_at=objective_node.created_at,
                    type=goal_type_str,
                    deadline=objective_node.deadline,
                    sub_tasks=[SubTask(**t) for t in objective_node.sub_tasks],
                    status=objective_node.state.value
                )

                next_task = get_next_actionable_task(goal)

                if next_task:
                    action_item = {
                        "id": next_task.id,
                        "description": f"[{goal.title}] {next_task.description}",
                        "estimated_time": next_task.estimated_time,
                        "difficulty": next_task.difficulty,
                        "question_type": "yes_no",
                        "metadata": {"goal_id": goal.id, "subtask_id": next_task.id}
                    }

                    if goal.type == GoalType.FLOURISHING:
                        action_item["priority"] = "flourishing_session"
                        action_item["description"] = f"🌟 [Deep Work] {next_task.description}"
                        action_item["verification"] = {
                            "type": "manual_confirm",
                            "message": "Did you achieve Flow?",
                        }
                        l2_actions.append(action_item)
                    else:
                        action_item["priority"] = "substrate_task"
                        action_item["verification"] = self._guess_verification(
                            next_task.description
                        )
                        l1_actions.append(action_item)
            except Exception as e:
                print(f"Error processing goal {objective_node.id}: {e}")
                continue

        return l1_actions, l2_actions

    def _infer_missing_goals(self) -> List[Dict]:
        """
        [Steward Upgrade] Proactively infer Vision and Goals using LLM engines.
        Writes directly to GoalRegistry with PENDING_CONFIRMATION state.
        Returns: A list of maintenance actions (e.g. notifications), not the goals themselves.
        """
        actions = []
        registry = self.registry

        # 1. Infer Vision if missing
        if not registry.visions:
            try:
                from core.strategic_engine.vision_inference import infer_vision
                # Enable search for better context
                vision_inf = infer_vision(self.state, enable_search=True)

                if vision_inf:
                    vision_node = ObjectiveNode(
                        id=f"vis_{str(uuid.uuid4())[:8]}",
                        title=vision_inf.title,
                        description=vision_inf.description,
                        layer=GoalLayer.VISION,
                        state=GoalState.ACTIVE, # Vision is active by default (foundational)
                        source=GoalSource.SYSTEM
                    )
                    registry.add_node(vision_node)
                    print(f"[Steward] Inferred Vision: {vision_node.title}")

                    actions.append({
                        "id": f"notify_vision_{datetime.now().strftime('%H%M%S')}",
                        "description": f"🌟 新愿景已确立: {vision_node.title}",
                        "priority": "maintenance",
                        "auto": True
                    })
            except Exception as e:
                print(f"[Steward] Vision inference failed: {e}")

        # 2. Infer Goals if no active/pending goals exist
        # Check if we have enough active work (Active or Pending Confirmation)
        active_or_pending = [
            g for g in registry.goals
            if g.state in [GoalState.ACTIVE, GoalState.VISION_PENDING_CONFIRMATION]
        ]

        if not active_or_pending:
            try:
                from core.goal_inference import infer_goals_from_state
                inferred_goals = infer_goals_from_state(self.state)

                for ig in inferred_goals:
                    pending_id = f"auto_{str(uuid.uuid4())[:6]}"
                    goal_node = ObjectiveNode(
                        id=pending_id,
                        title=ig.title,
                        description=ig.description,
                        layer=GoalLayer.GOAL,
                        state=GoalState.VISION_PENDING_CONFIRMATION, # Requires User Confirm
                        source=GoalSource.SYSTEM
                    )
                    # Link to Vision if exists
                    if registry.visions:
                        goal_node.parent_id = registry.visions[0].id

                    registry.add_node(goal_node)
                    print(f"[Steward] Inferred Goal: {goal_node.title}")

                    actions.append({
                        "id": f"notify_goal_{pending_id}",
                        "description": f"💡 新提案待确认: {goal_node.title}",
                        "priority": "maintenance",
                        "auto": True
                    })
            except Exception as e:
                print(f"[Steward] Goal inference failed: {e}")
                actions.append({
                    "id": f"notify_error_{uuid.uuid4()}",
                    "description": f"⚠️ 思考过程出错: {str(e)}",
                    "priority": "maintenance",
                    "auto": True
                })
        else:
             actions.append({
                "id": f"notify_info_{uuid.uuid4()}",
                "description": "🧠 思考完毕: 当前已有活跃目标，建议专注当下。",
                "priority": "maintenance",
                "auto": True
            })

        return actions

    def _generate_rhythm_actions(self) -> List[Dict[str, Any]]:
        """Generate habit actions."""
        # ... (Same logic as before, just treating as substrate_task usually) ...
        # For brevity, reusing the logic but mapping to new priority
        actions = []
        llm = get_llm("simple_local")
        if llm.get_model_name() == "rule_based":
            return actions

        system_prompt = load_prompt("rhythm_analysis")
        if not system_prompt:
            return actions

        from core.event_sourcing import EVENT_LOG_PATH
        recent_events = []
        if EVENT_LOG_PATH.exists():
             with open(EVENT_LOG_PATH, "r", encoding="utf-8") as f:
                lines = f.readlines()[-config.EVENT_LOOKBACK:]
                for line in lines:
                    try:
                        recent_events.append(json.loads(line.strip()))
                    except json.JSONDecodeError:
                        continue

        if len(recent_events) < config.MIN_EVENTS_FOR_RHYTHM:
            return actions

        prompt = (
            f"事件日志:\n{json.dumps(recent_events, ensure_ascii=False, indent=2)}\n\n"
            f"当前状态:\n{json.dumps(self.state, ensure_ascii=False, indent=2)}"
        )

        try:
            response = llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=0.3,
                max_tokens=800
            )
            if response.success and response.content:
                 result = parse_llm_json(response.content)
                 if result:
                     habits = result.get("detected_habits", [])

                     for habit in habits[:config.MAX_RHYTHM_ACTIONS]:
                        pattern = habit.get("pattern", "日常习惯")
                        actions.append({
                            "id": f"rhythm_{datetime.now().strftime('%Y%m%d')}_{len(actions)}",
                            "description": f"执行惯例: {pattern}",
                            # Habits are usually substrate
                            "priority": "substrate_task",
                            "question_type": "yes_no",
                            "confidence": habit.get("confidence", 0.5)
                        })
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger("steward")
            logger.warning(f"习惯检测失败: {e}")

        return actions

    def _generate_exploration_actions(self) -> List[Dict[str, Any]]:
        """Generate new exploratory actions using LLM."""
        actions = []

        # Use strategic brain for high-level exploration
        llm = get_llm("strategic_brain")
        if llm.get_model_name() == "rule_based":
            # 规则模式：使用简单启发式
            time_blocks = self._get_field("inventory.time_blocks") or []
            if time_blocks:
                actions.append({
                    "id": f"explore_{datetime.now().strftime('%Y%m%d')}",
                    "description": "利用空闲时间进行学习",
                    "priority": "exploration",
                    "question_type": "yes_no"
                })
            return actions

        # LLM 模式：生成个性化建议
        system_prompt_template = load_prompt("exploration_suggest")
        if not system_prompt_template:
            return actions

        system_prompt = system_prompt_template.format(
            min_task_duration=config.MIN_TASK_DURATION
        )

        # 构建上下文
        identity = self._get_field("identity") or {}
        skills = self._get_field("capability.skills") or []
        time_blocks = self._get_field("inventory.time_blocks") or []
        constraints = self._get_field("constraints") or {}

        prompt = f"""用户身份:
{json.dumps(identity, ensure_ascii=False, indent=2)}

已掌握技能:
{json.dumps(skills, ensure_ascii=False)}

可用时间块:
{json.dumps(time_blocks, ensure_ascii=False)}

约束条件:
{json.dumps(constraints, ensure_ascii=False, indent=2)}

请根据以上信息生成 1-2 个探索性行动建议。"""

        try:
            response = llm.generate(
                prompt=prompt,
                system_prompt=system_prompt,
                temperature=config.EXPLORATION_TEMPERATURE,
                max_tokens=600
            )

            if response.success and response.content:
                try:
                    result = parse_llm_json(response.content)
                    if result:
                        suggestions = result.get("suggestions", [])

                        for i, sug in enumerate(suggestions[:config.MAX_EXPLORATION_ACTIONS]):
                            actions.append({
                                "id": f"explore_{datetime.now().strftime('%Y%m%d')}_{i}",
                                "description": sug.get("description", "探索新领域"),
                                "priority": "exploration",
                                "question_type": "yes_no",
                                "estimated_time": sug.get("estimated_time"),
                                "rationale": sug.get("rationale")
                            })
                    else:
                        self._add_fallback_exploration(actions)
                except (json.JSONDecodeError, KeyError):
                    # 解析失败，使用默认建议
                    self._add_fallback_exploration(actions)
        except Exception as e:
            from core.logger import get_logger
            logger = get_logger("steward")
            logger.warning(f"探索建议服务调用失败: {e}，已降级为仅基础功能")
            self._add_fallback_exploration(actions)

        return actions

    def _add_fallback_exploration(self, actions: List[Dict[str, Any]]) -> None:
        """Helper to add fallback exploration action."""
        # 定义一个容易验证的任务：写学习日志
        log_file = config.DEFAULT_LOG_PATH

        actions.append({
            "id": f"explore_{datetime.now().strftime('%Y%m%d')}",
            "description": f"执行: 写 3 行学习笔记 ({log_file})",
            "priority": "exploration",
            "question_type": "yes_no",

            # Phase 7: Verification Metadata
            "verification": {
                "type": "file_system",
                "target": log_file
            }
        })

    def _guess_verification(self, description: str) -> Optional[Dict[str, Any]]:
        """Semantic action classification using LLM (replaces keyword matching)."""
        from core.semantic_classifier import classify_action
        return classify_action(description)

    def _handle_idle_state(self) -> List[Dict[str, Any]]:
        """
        [Layered Defense] Handle system idle state by generating a BHB Engagement Task.
        Instead of returning static text, we use the LLM to generate a context-aware
        micro-action or reflection based on the Better Human Blueprint.
        """
        phase = self._get_current_phase()

        # 1. Load BHB Config
        bhb_config = parse_bhb()

        # 2. Context Construction
        context_summary = f"Current Phase: {phase}. "
        if self.state.get("metrics"):
             context_summary += f"Energy: {self.state['metrics'].get('energy', 'N/A')}. "

        # 3. Prompt Construction
        llm = get_llm("strategic_brain")
        prompt_template = load_prompt("bhb_engagement")

        if not prompt_template:
            # Fallback if prompt missing
            return [{
                "id": f"bhb_fallback_{uuid.uuid4()}",
                "description": "系统提示缺失 (bhb_engagement)，请检查配置。",
                "priority": "maintenance"
            }]

        prompt = prompt_template.format(
            current_time=datetime.now().strftime("%H:%M"),
            energy_phase=phase,
            context_summary=context_summary,
            bhb_philosophy=bhb_config.philosophy,
            bhb_goals="\n".join(bhb_config.strategic_goals)
        )

        try:
             # Higher temperature for variety
             response = llm.generate(prompt, temperature=0.85)
             if response.success:
                 result = parse_llm_json(response.content)
                 if result:
                     # 4. Register as Goal (Agentic Behavior - Optional, but good for tracking)
                     # For micro-actions, we might just return the action item directly
                     # without polluting the Goal Registry with tiny tasks.

                     action_id = f"bhb_{str(uuid.uuid4())[:8]}"
                     title = result.get("title", "BHB Engagement")
                     desc = result.get("description", "时刻保持觉知。")
                     priority = result.get("priority", "substrate_task")

                     # Create Action Item
                     return [{
                         "id": action_id,
                         "description": (
                             f"🌱 [{result.get('type', 'Activity').upper()}] "
                             f"{title}: {desc}"
                         ),
                         "priority": priority,
                         "verification": {"type": "manual_confirm"},
                         "metadata": {"source": "Better Human Blueprint"}
                     }]
        except Exception as e:
            print(f"BHB Engagement gen failed: {e}")

        # Layer 4 Safety Net (Action Level) - If LLM fails,
        # still return something better than "Idle"
        return [{
            "id": "bhb_fallback_safe",
            "description": "💡哪怕是简单的深呼吸，也是对当下的回归。",
            "priority": "maintenance"
        }]
