"""
User I/O for AI Life OS.

Strict interface layer that enforces schema validation.
Rejects any subjective or non-conforming input.
"""
from typing import Any, Dict

from interface.schema import InputSchema, InputType, ALLOWED_SCHEMAS


def ask_user(
    action: Dict[str, Any],
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Ask user a question with strict schema validation.

    Args:
        action: Action dictionary containing question type and description.
        max_retries: Maximum retry attempts for invalid input.

    Returns:
        Response dictionary with validated value and metadata.
    """
    description = action.get("description", "")

    # Get or create schema
    schema = _get_schema_for_action(action)

    print(f"\n◈ [指令下达] {description}")
    print(f"  [等待反馈] {schema.prompt}")

    if schema.options:
        for i, opt in enumerate(schema.options, 1):
            print(f"  [{i}] {opt}")

    for attempt in range(max_retries):
        try:
            user_input = input(">> ").strip()
        except (EOFError, KeyboardInterrupt):
            return {
                "action_id": action.get("id"),
                "success": False,
                "failure_type": "skipped",
                "reason": "User interrupted"
            }

        is_valid, result = schema.validate(user_input)

        if is_valid:
            if schema.input_type == InputType.YES_NO and result is False:
                 # If user says "No", ask for reason (Feedback)
                 print("  [异常处理] 请输入未完成原因 (可选):")
                 reason = input(">> ").strip()
                 return {
                    "action_id": action.get("id"),
                    "success": False,
                    "measure": result,
                    "reason": reason
                 }

            return {
                "action_id": action.get("id"),
                "success": True,
                "value": result,
                "raw_input": user_input
            }
        else:
            remaining = max_retries - attempt - 1
            if remaining > 0:
                print(f"  [输入错误] {result} (剩余重试: {remaining})")
            else:
                print(f"  [输入错误] {result}")

    # Max retries exceeded
    return {
        "action_id": action.get("id"),
        "success": False,
        "failure_type": "invalid_input",
        "reason": "Max retries exceeded"
    }


def _get_schema_for_action(action: Dict[str, Any]) -> InputSchema:
    """
    Get appropriate schema for an action.

    Args:
        action: Action dictionary.

    Returns:
        InputSchema for validating user input.
    """
    question_type = action.get("question_type", "yes_no")
    target_field = action.get("target_field", "")

    # Check for pre-defined schema
    if target_field in ALLOWED_SCHEMAS:
        return ALLOWED_SCHEMAS[target_field]

    # Build schema from question type
    if question_type == "yes_no":
        return InputSchema(
            input_type=InputType.YES_NO,
            prompt="[Y]已执行 / [N]拒绝或失败"
        )
    elif question_type == "number":
        return InputSchema(
            input_type=InputType.NUMBER,
            prompt="请输入数值"
        )
    elif question_type == "time_range":
        return InputSchema(
            input_type=InputType.TIME_RANGE,
            prompt="请输入时间范围 (HH:MM-HH:MM)"
        )
    elif question_type == "text":
        return InputSchema(
            input_type=InputType.TEXT,
            prompt="请输入文本信息"
        )
    elif question_type == "confirm_vision":
        return InputSchema(
            input_type=InputType.YES_NO,
            prompt="[Y]确认采用此战略方向 / [N]拒绝"
        )
    else:
        # Default to yes/no
        return InputSchema(
            input_type=InputType.YES_NO,
            prompt="[Y]已执行 / [N]拒绝或失败"
        )


def display_plan(plan: Dict[str, Any]) -> None:
    """
    Display the generated plan to user.

    Args:
        plan: Plan dictionary from planner.
    """
    print("\n" + "=" * 60)
    print("⚡ AI LIFE OS // 每日指令清单 (SYSTEM MANIFEST)")
    print("=" * 60)

    actions = plan.get("actions", [])

    if not actions:
        print("  [状态] 今日无待执行指令 (System Idle)")
        return

    for i, action in enumerate(actions, 1):
        priority = action.get("priority", "")
        # Sci-fi style icons
        priority_icon = {
            "maintenance":        "[MAINT]",  # Maintenance
            "flourishing_session": "[FLOW ]",  # L2 深度工作
            "substrate_task":      "[SUBS ]",  # L1 基础任务
            "rhythm":              "[CYCLE]",  # Rhythm/Habit
            "exploration":         "[QUEST]"   # Exploration
        }.get(priority, "[TASK ]")

        print(f"  {i:02d}. {priority_icon} {action.get('description', '')}")

    print("-" * 60)
    print(f"  [校验码] {plan.get('generated_at', 'UNKNOWN')}")
    print("=" * 60)

    # Show audit info if bootstrap
    if plan.get("is_bootstrap"):
        print("\n🔰 [系统初始化] 检测到首次运行，需要录入基础档案...")


def display_message(message: str, level: str = "info") -> None:
    """
    Display a system message.

    Args:
        message: Message text.
        level: One of 'info', 'warning', 'error'.
    """
    prefix = {
        "info":    "ℹ️ [INFO ]",
        "warning": "⚠️ [WARN ]",
        "error":   "❌ [ERROR]",
    }.get(level, "[INFO ]")

    print(f"{prefix} {message}")

    # Send system notification for important messages
    if level in ["warning", "error"]:
        try:
            from interface.notifiers.desktop_notifier import DesktopNotifier
            from interface.notifiers.base import Notification, NotificationPriority

            notifier = DesktopNotifier()
            priority = (
                NotificationPriority.HIGH
                if level == "error"
                else NotificationPriority.NORMAL
            )

            notifier.send(Notification(
                title=f"AI Life OS [{level.upper()}]",
                message=message,
                priority=priority
            ))
        except ImportError:
            pass  # Fail silently if notifiers not available
