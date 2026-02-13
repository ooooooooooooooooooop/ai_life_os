"""
Input Schema for AI Life OS.

Defines strict input types for user interaction.
All user inputs must conform to these schemas.
"""
from enum import Enum
from typing import Any, Dict, List, Optional
from dataclasses import dataclass


class InputType(Enum):
    """Allowed input types."""
    YES_NO = "yes_no"
    NUMBER = "number"
    TIME_RANGE = "time_range"
    ENUM = "enum"
    TEXT = "text"  # Restricted: only for specific data collection
    # 第三阶段新增
    DURATION = "duration"  # 时长输入，如 "30分钟", "1小时"
    DATE = "date"  # 日期输入，如 "2026-01-26"
    LOCATION = "location"  # 地点输入


@dataclass
class InputSchema:
    """Schema definition for a single input."""
    input_type: InputType
    prompt: str
    options: Optional[List[str]] = None  # For ENUM type
    min_value: Optional[float] = None    # For NUMBER type
    max_value: Optional[float] = None    # For NUMBER type

    def validate(self, user_input: str) -> tuple[bool, Any]:
        """
        Validate user input against this schema.

        Args:
            user_input: Raw string input from user.

        Returns:
            Tuple of (is_valid, parsed_value or error_message)
        """
        user_input = user_input.strip()

        if self.input_type == InputType.YES_NO:
            return self._validate_yes_no(user_input)
        elif self.input_type == InputType.NUMBER:
            return self._validate_number(user_input)
        elif self.input_type == InputType.TIME_RANGE:
            return self._validate_time_range(user_input)
        elif self.input_type == InputType.ENUM:
            return self._validate_enum(user_input)
        elif self.input_type == InputType.TEXT:
            return self._validate_text(user_input)
        elif self.input_type == InputType.DURATION:
            return self._validate_duration(user_input)
        elif self.input_type == InputType.DATE:
            return self._validate_date(user_input)
        elif self.input_type == InputType.LOCATION:
            return self._validate_location(user_input)
        else:
            return False, f"Unknown input type: {self.input_type}"

    def _validate_yes_no(self, user_input: str) -> tuple[bool, Any]:
        """Validate yes/no input."""
        normalized = user_input.lower()

        yes_variants = ["yes", "y", "是", "对", "1", "true"]
        no_variants = ["no", "n", "否", "不", "0", "false"]

        if normalized in yes_variants:
            return True, True
        elif normalized in no_variants:
            return True, False
        else:
            return False, "请输入 是/否 或 yes/no"

    def _validate_number(self, user_input: str) -> tuple[bool, Any]:
        """Validate numeric input."""
        try:
            value = float(user_input)

            if self.min_value is not None and value < self.min_value:
                return False, f"数值必须 >= {self.min_value}"
            if self.max_value is not None and value > self.max_value:
                return False, f"数值必须 <= {self.max_value}"

            return True, value
        except ValueError:
            return False, "请输入有效数字"

    def _validate_time_range(self, user_input: str) -> tuple[bool, Any]:
        """
        Validate time range input.
        Expected format: "HH:MM-HH:MM" or "HH:MM - HH:MM"
        """
        import re

        # Pattern: 09:00-18:00 or 09:00 - 18:00
        pattern = r"^(\d{1,2}):(\d{2})\s*-\s*(\d{1,2}):(\d{2})$"
        match = re.match(pattern, user_input)

        if not match:
            return False, "请输入时间范围，格式如 09:00-18:00"

        start_hour, start_min, end_hour, end_min = map(int, match.groups())

        if not (0 <= start_hour <= 23 and 0 <= start_min <= 59):
            return False, "开始时间无效"
        if not (0 <= end_hour <= 23 and 0 <= end_min <= 59):
            return False, "结束时间无效"

        return True, {
            "start": f"{start_hour:02d}:{start_min:02d}",
            "end": f"{end_hour:02d}:{end_min:02d}"
        }

    def _validate_enum(self, user_input: str) -> tuple[bool, Any]:
        """Validate enum input."""
        if not self.options:
            return False, "No options defined for enum"

        # Allow index or exact match
        if user_input.isdigit():
            idx = int(user_input) - 1  # 1-indexed for user
            if 0 <= idx < len(self.options):
                return True, self.options[idx]

        if user_input in self.options:
            return True, user_input

        return False, f"请选择: {', '.join(self.options)}"

    def _validate_text(self, user_input: str) -> tuple[bool, Any]:
        """
        Validate text input.

        Note: Text is only allowed for specific data collection (identity, etc.)
        Not for subjective opinions.
        """
        if len(user_input) < 1:
            return False, "输入不能为空"
        if len(user_input) > 200:
            return False, "输入过长 (最多200字符)"

        return True, user_input

    def _validate_duration(self, user_input: str) -> tuple[bool, Any]:
        """
        Validate duration input.
        Accepts formats like: "30分钟", "1小时", "1.5h", "90min"
        """
        import re

        # 标准化输入
        normalized = user_input.lower().strip()

        # 中文格式: 30分钟, 1小时, 1小时30分钟
        cn_pattern = r"^(\d+(?:\.\d+)?)\s*(分钟|小时|分|时)(?:(\d+)\s*(分钟|分))?$"
        cn_match = re.match(cn_pattern, normalized)

        if cn_match:
            value = float(cn_match.group(1))
            unit = cn_match.group(2)

            if unit in ["小时", "时"]:
                minutes = value * 60
            else:
                minutes = value

            # 检查额外的分钟
            if cn_match.group(3):
                minutes += int(cn_match.group(3))

            return True, {"minutes": int(minutes), "display": user_input}

        # 英文格式: 30min, 1h, 1.5h
        en_pattern = r"^(\d+(?:\.\d+)?)\s*(min|m|hour|h|hr)s?$"
        en_match = re.match(en_pattern, normalized)

        if en_match:
            value = float(en_match.group(1))
            unit = en_match.group(2)

            if unit in ["hour", "h", "hr"]:
                minutes = value * 60
            else:
                minutes = value

            return True, {"minutes": int(minutes), "display": user_input}

        # 纯数字默认为分钟
        if normalized.isdigit():
            return True, {"minutes": int(normalized), "display": f"{normalized}分钟"}

        return False, "请输入时长，如: 30分钟, 1小时, 1.5h"

    def _validate_date(self, user_input: str) -> tuple[bool, Any]:
        """
        Validate date input.
        Accepts formats like: "2026-01-26", "01/26", "明天", "下周一"
        """
        from datetime import datetime, timedelta
        import re

        normalized = user_input.strip()
        today = datetime.now()

        # 相对日期
        relative_dates = {
            "今天": today,
            "明天": today + timedelta(days=1),
            "后天": today + timedelta(days=2),
            "大后天": today + timedelta(days=3),
        }

        if normalized in relative_dates:
            date = relative_dates[normalized]
            return True, date.strftime("%Y-%m-%d")

        # ISO 格式: 2026-01-26
        iso_pattern = r"^(\d{4})-(\d{1,2})-(\d{1,2})$"
        iso_match = re.match(iso_pattern, normalized)

        if iso_match:
            try:
                year, month, day = map(int, iso_match.groups())
                date = datetime(year, month, day)
                return True, date.strftime("%Y-%m-%d")
            except ValueError:
                return False, "日期无效"

        # 简写格式: 01/26 或 1-26 (默认今年)
        short_pattern = r"^(\d{1,2})[/\-](\d{1,2})$"
        short_match = re.match(short_pattern, normalized)

        if short_match:
            try:
                month, day = map(int, short_match.groups())
                date = datetime(today.year, month, day)
                return True, date.strftime("%Y-%m-%d")
            except ValueError:
                return False, "日期无效"

        return False, "请输入日期，如: 2026-01-26, 明天, 01/26"

    def _validate_location(self, user_input: str) -> tuple[bool, Any]:
        """
        Validate location input.
        Similar to text but with location-specific constraints.
        """
        if len(user_input) < 1:
            return False, "请输入地点"
        if len(user_input) > 100:
            return False, "地点名称过长"

        # 基本清洗
        location = user_input.strip()

        return True, {"name": location, "type": "text"}


# Pre-defined schemas for common questions
ALLOWED_SCHEMAS: Dict[str, InputSchema] = {
    "task_completion": InputSchema(
        input_type=InputType.YES_NO,
        prompt="今天是否完成了此任务？"
    ),
    "city": InputSchema(
        input_type=InputType.TEXT,
        prompt="请输入您所在的城市名称"
    ),
    "occupation": InputSchema(
        input_type=InputType.TEXT,
        prompt="请输入您的职业或主要身份"
    ),
    "work_hours": InputSchema(
        input_type=InputType.TIME_RANGE,
        prompt="请输入您的工作时间 (格式: 09:00-18:00)"
    ),
}
