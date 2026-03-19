"""
自我进化引擎核心模块。

该模块负责系统的自我优化能力，通过分析历史数据生成并验证新的规则。

主要功能：
- observe(): 观察系统行为模式
- generate_rule(): 生成进化规则
- validate_rule(): 验证规则有效性
- apply_rule(): 应用通过验证的规则
"""
import ast
import json
import os
import logging
import hashlib
import random
import string
import shutil
from datetime import datetime, timedelta
from typing import Dict, Tuple, List, Optional
from pathlib import Path

from core.exceptions import AILifeError, ValidationError, FileOperationError
from core.logger import get_logger


# ========== 异常定义 ==========

class EvolutionError(AILifeError):
    """进化引擎基础异常。"""

    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(message, hint)


class InvalidObservationError(EvolutionError):
    """观察结论格式无效。"""

    def __init__(self, message: str, observation_data: Optional[Dict] = None):
        hint = "观察结论格式不符合要求，请检查LLM返回的JSON结构"
        super().__init__(message, hint)
        self.observation_data = observation_data


class LLMServiceError(EvolutionError):
    """LLM服务调用失败。"""

    def __init__(self, message: str, service_name: Optional[str] = None):
        hint = "LLM服务调用失败，请检查服务状态和网络连接"
        super().__init__(message, hint)
        self.service_name = service_name


class InvalidHookError(EvolutionError):
    """Hook点不合法。"""

    def __init__(self, message: str, hook_name: Optional[str] = None):
        hint = f"Hook点 '{hook_name}' 不在允许列表中" if hook_name else "Hook点不合法"
        super().__init__(message, hint)
        self.hook_name = hook_name


class RuleNotValidatedError(EvolutionError):
    """规则未通过验证。"""

    def __init__(self, message: str, rule_id: Optional[str] = None):
        hint = "规则必须通过验证才能应用"
        super().__init__(message, hint)
        self.rule_id = rule_id


class FileWriteError(EvolutionError):
    """文件写入失败。"""

    def __init__(self, message: str, file_path: Optional[str] = None):
        hint = f"文件写入失败: {file_path}" if file_path else "文件写入失败"
        super().__init__(message, hint)
        self.file_path = file_path


class ManifestUpdateError(EvolutionError):
    """manifest.json更新失败。"""

    def __init__(self, message: str, manifest_path: Optional[str] = None):
        hint = "manifest.json更新失败，请检查文件权限和格式"
        super().__init__(message, hint)
        self.manifest_path = manifest_path


# ========== 常量定义 ==========

# 允许的Hook点列表
ALLOWED_HOOKS = [
    "signal_detector",
    "mood_detector",
    "intervention_level"
]

# Hook接口签名规范
HOOK_SIGNATURES = {
    "signal_detector": {
        "function_name": "detect_signal",
        "parameters": [
            {"name": "context", "type": "dict"}
        ],
        "return_type": "dict",
        "required_return_fields": [
            "signal_detected",
            "signal_type",
            "severity",
            "description"
        ]
    },
    "mood_detector": {
        "function_name": "detect_mood",
        "parameters": [
            {"name": "context", "type": "dict"}
        ],
        "return_type": "dict",
        "required_return_fields": [
            "mood_detected",
            "mood_type",
            "intensity",
            "suggestion"
        ]
    },
    "intervention_level": {
        "function_name": "determine_level",
        "parameters": [
            {"name": "context", "type": "dict"}
        ],
        "return_type": "dict",
        "required_return_fields": [
            "intervention_needed",
            "level",
            "timing",
            "method"
        ]
    }
}

# 规则存储路径
RULES_DIR = Path(__file__).parent.parent / "skills" / "evolved"
MANIFEST_PATH = RULES_DIR / "manifest.json"

# Blueprint文件路径（只读）
BLUEPRINT_PATH = Path(__file__).parent.parent / "docs" / "concepts" / "better_human_blueprint.md"

# USER.md文件路径
USER_MD_PATH = Path(__file__).parent.parent / "USER.md"

# 事件日志路径
EVENT_LOG_PATH = Path(__file__).parent.parent / "logs" / "event_log.jsonl"


# ========== 日志配置 ==========

logger = get_logger("evolution_engine")


# ========== 辅助函数 ==========

def generate_rule_id() -> str:
    """
    生成唯一的规则ID。

    格式: rule_{timestamp}_{random_8chars}

    Returns:
        唯一的规则ID字符串
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    random_chars = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"rule_{timestamp}_{random_chars}"


def validate_observation_format(observation: Dict) -> Tuple[bool, str]:
    """
    验证观察结论的格式。

    Args:
        observation: 观察结论字典

    Returns:
        (是否有效, 错误信息)
    """
    required_fields = ["pattern", "confidence", "evidence", "suggested_action"]

    for field in required_fields:
        if field not in observation:
            return False, f"缺少必填字段: {field}"

    # 验证pattern
    if not isinstance(observation["pattern"], str) or len(observation["pattern"]) == 0:
        return False, "pattern必须为非空字符串"

    if len(observation["pattern"]) > 500:
        return False, "pattern长度不能超过500字符"

    # 验证confidence
    if not isinstance(observation["confidence"], (int, float)):
        return False, "confidence必须为数值"

    if not 0 <= observation["confidence"] <= 1:
        return False, "confidence取值范围必须在[0, 1]之间"

    # 验证evidence
    if not isinstance(observation["evidence"], list) or len(observation["evidence"]) == 0:
        return False, "evidence必须为非空数组"

    for evidence in observation["evidence"]:
        if not isinstance(evidence, str):
            return False, "evidence数组中的每个元素必须为字符串"

    # 验证suggested_action
    if not isinstance(observation["suggested_action"], str) or len(observation["suggested_action"]) == 0:
        return False, "suggested_action必须为非空字符串"

    if len(observation["suggested_action"]) > 200:
        return False, "suggested_action长度不能超过200字符"

    return True, ""


def validate_rule_format(rule: Dict) -> Tuple[bool, str]:
    """
    验证规则对象的格式。

    Args:
        rule: 规则字典

    Returns:
        (是否有效, 错误信息)
    """
    required_fields = ["rule_id", "code", "target_hook", "description", "confidence"]

    for field in required_fields:
        if field not in rule:
            return False, f"缺少必填字段: {field}"

    # 验证rule_id
    if not isinstance(rule["rule_id"], str) or len(rule["rule_id"]) == 0:
        return False, "rule_id必须为非空字符串"

    # 验证code
    if not isinstance(rule["code"], str) or len(rule["code"]) == 0:
        return False, "code必须为非空字符串"

    # 验证target_hook
    if rule["target_hook"] not in ALLOWED_HOOKS:
        return False, f"target_hook必须在允许列表中: {ALLOWED_HOOKS}"

    # 验证description
    if not isinstance(rule["description"], str) or len(rule["description"]) == 0:
        return False, "description必须为非空字符串"

    if len(rule["description"]) > 300:
        return False, "description长度不能超过300字符"

    # 验证confidence
    if not isinstance(rule["confidence"], (int, float)):
        return False, "confidence必须为数值"

    if not 0 <= rule["confidence"] <= 1:
        return False, "confidence取值范围必须在[0, 1]之间"

    return True, ""


# ========== 主函数（占位，将在后续任务中实现） ==========

def observe(days: int = 30) -> Dict:
    """
    观察系统行为模式。

    Args:
        days: 观察的天数范围，默认30天

    Returns:
        结构化观察结论字典

    Raises:
        InvalidObservationError: 观察结论格式无效
        LLMServiceError: LLM服务调用失败
        FileOperationError: 文件读取失败
    """
    logger.info(f"开始观察系统行为模式，观察范围: 最近{days}天")

    # 1. 读取事件日志
    event_log_content = _read_event_log(days)
    if not event_log_content:
        logger.warning("事件日志缺失或为空，返回空观察结论")
        return {
            "pattern": "无可用数据",
            "confidence": 0.0,
            "evidence": [],
            "suggested_action": "等待更多事件日志积累"
        }

    # 2. 读取USER.md
    user_md_content = _read_user_md()

    # 3. 读取Blueprint（只读）
    blueprint_content = _read_blueprint()

    # 4. 构造LLM prompt
    prompt = _build_observation_prompt(
        event_log_content,
        user_md_content,
        blueprint_content,
        days
    )

    # 5. 调用LLM服务
    logger.info("调用LLM服务进行行为模式归纳")
    try:
        from core.llm_adapter import create_llm_adapter

        llm = create_llm_adapter(profile_name="smart")
        response = llm.generate(
            prompt=prompt,
            system_prompt="你是一个AI系统的行为分析专家。",
            temperature=0.7,
            max_tokens=2000
        )

        if not response.success:
            raise LLMServiceError(
                f"LLM调用失败: {response.error}",
                service_name=llm.get_model_name()
            )

        logger.info("LLM调用成功，开始解析返回结果")

    except Exception as e:
        logger.error(f"LLM服务调用异常: {str(e)}")
        raise LLMServiceError(f"LLM服务调用异常: {str(e)}")

    # 6. 解析LLM返回的JSON
    try:
        # 提取JSON内容（可能包含在markdown代码块中）
        content = response.content.strip()
        if "```json" in content:
            # 提取markdown代码块中的JSON
            start = content.find("```json") + 7
            end = content.find("```", start)
            content = content[start:end].strip()
        elif "```" in content:
            # 提取普通代码块中的JSON
            start = content.find("```") + 3
            end = content.find("```", start)
            content = content[start:end].strip()

        observation = json.loads(content)

    except json.JSONDecodeError as e:
        logger.error(f"JSON解析失败: {str(e)}")
        logger.error(f"LLM返回内容: {response.content[:500]}")
        raise InvalidObservationError(
            f"LLM返回的JSON格式无效: {str(e)}",
            observation_data={"raw_content": response.content[:500]}
        )

    # 7. 验证JSON格式和字段
    is_valid, error_msg = validate_observation_format(observation)
    if not is_valid:
        logger.error(f"观察结论格式验证失败: {error_msg}")
        raise InvalidObservationError(
            f"观察结论格式无效: {error_msg}",
            observation_data=observation
        )

    logger.info(f"观察完成，发现模式: {observation['pattern'][:100]}")
    return observation


def _read_event_log(days: int) -> str:
    """
    读取最近N天的事件日志。

    Args:
        days: 天数

    Returns:
        事件日志内容字符串
    """
    from core.paths import DATA_DIR

    event_log_path = DATA_DIR / "event_log.jsonl"

    if not event_log_path.exists():
        logger.warning(f"事件日志文件不存在: {event_log_path}")
        return ""

    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        events = []

        with open(event_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    # 检查事件时间是否在范围内
                    timestamp_str = event.get("timestamp", "")
                    if timestamp_str:
                        try:
                            event_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                            if event_time >= cutoff_date:
                                events.append(event)
                        except ValueError:
                            # 时间格式错误，跳过该事件
                            continue
                except json.JSONDecodeError:
                    # JSON格式错误，跳过该行
                    continue

        # 按时间倒序排序
        events.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

        # 限制事件数量，避免prompt过长
        max_events = 100
        if len(events) > max_events:
            events = events[:max_events]
            logger.info(f"事件数量过多，仅保留最近{max_events}条")

        # 转换为字符串
        return json.dumps(events, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.error(f"读取事件日志失败: {str(e)}")
        raise FileOperationError(f"读取事件日志失败: {str(e)}", file_path=str(event_log_path))


def _read_user_md() -> str:
    """
    读取USER.md用户画像。

    Returns:
        USER.md内容字符串
    """
    if not USER_MD_PATH.exists():
        logger.warning(f"USER.md文件不存在: {USER_MD_PATH}")
        return ""

    try:
        with open(USER_MD_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"成功读取USER.md，长度: {len(content)}字符")
        return content
    except Exception as e:
        logger.error(f"读取USER.md失败: {str(e)}")
        raise FileOperationError(f"读取USER.md失败: {str(e)}", file_path=str(USER_MD_PATH))


def _read_blueprint() -> str:
    """
    读取Blueprint约束文件（只读）。

    Returns:
        Blueprint内容字符串
    """
    if not BLUEPRINT_PATH.exists():
        logger.warning(f"Blueprint文件不存在: {BLUEPRINT_PATH}，使用默认约束")
        return "【默认约束】系统应尊重用户自主性，避免过度干预。"

    try:
        # 以只读模式打开
        with open(BLUEPRINT_PATH, "r", encoding="utf-8") as f:
            content = f.read()
        logger.info(f"成功读取Blueprint（只读），长度: {len(content)}字符")
        return content
    except Exception as e:
        logger.error(f"读取Blueprint失败: {str(e)}")
        # Blueprint读取失败不抛出异常，使用默认约束
        return "【默认约束】系统应尊重用户自主性，避免过度干预。"


def _build_observation_prompt(
    event_log: str,
    user_md: str,
    blueprint: str,
    days: int
) -> str:
    """
    构造观察Prompt。

    Args:
        event_log: 事件日志内容
        user_md: USER.md内容
        blueprint: Blueprint内容
        days: 观察天数

    Returns:
        完整的prompt字符串
    """
    prompt = f"""你是一个AI系统的行为分析专家。你的任务是分析系统运行数据，归纳出有价值的行为模式。

【核心约束】
以下Blueprint内容是系统的核心价值观，不可修改，你的建议不得与之冲突：
{blueprint}

【用户画像】
{user_md if user_md else "（无用户画像数据）"}

【事件日志】（最近{days}天）
{event_log}

请分析以上数据，归纳出一个行为模式，输出JSON格式：
{{
  "pattern": "行为模式的文字描述",
  "confidence": 0.85,
  "evidence": ["证据1", "证据2", "证据3"],
  "suggested_action": "建议的行动"
}}

注意：
1. pattern应具体、可操作
2. confidence基于证据的数量和质量
3. evidence必须来自事件日志
4. suggested_action不得违反Blueprint约束
"""
    return prompt


def generate_rule(observation: Dict) -> Dict:
    """
    基于观察结论生成进化规则。

    Args:
        observation: observe()返回的观察结论

    Returns:
        规则对象字典

    Raises:
        InvalidObservationError: 观察结论格式无效
        LLMServiceError: LLM服务调用失败
        InvalidHookError: 生成的hook点不合法
    """
    logger.info("开始生成进化规则")

    # 1. 验证观察结论格式
    is_valid, error_msg = validate_observation_format(observation)
    if not is_valid:
        logger.error(f"观察结论格式验证失败: {error_msg}")
        raise InvalidObservationError(
            f"观察结论格式无效: {error_msg}",
            observation_data=observation
        )

    # 2. 构造LLM prompt
    prompt = _build_generation_prompt(observation)

    # 3. 实现重试机制（最多3次）
    max_retries = 3
    for attempt in range(max_retries):
        logger.info(f"调用LLM生成规则，尝试 {attempt + 1}/{max_retries}")

        try:
            from core.llm_adapter import create_llm_adapter

            llm = create_llm_adapter(profile_name="smart")
            response = llm.generate(
                prompt=prompt,
                system_prompt="你是一个Python代码生成专家。",
                temperature=0.7,
                max_tokens=2000
            )

            if not response.success:
                logger.warning(f"LLM调用失败: {response.error}")
                if attempt < max_retries - 1:
                    continue
                raise LLMServiceError(
                    f"LLM调用失败: {response.error}",
                    service_name=llm.get_model_name()
                )

            # 4. 解析LLM返回的JSON
            try:
                content = response.content.strip()
                if "```json" in content:
                    start = content.find("```json") + 7
                    end = content.find("```", start)
                    content = content[start:end].strip()
                elif "```" in content:
                    start = content.find("```") + 3
                    end = content.find("```", start)
                    content = content[start:end].strip()

                rule = json.loads(content)

            except json.JSONDecodeError as e:
                logger.warning(f"JSON解析失败: {str(e)}")
                if attempt < max_retries - 1:
                    continue
                raise InvalidObservationError(
                    f"LLM返回的JSON格式无效: {str(e)}",
                    observation_data={"raw_content": response.content[:500]}
                )

            # 5. 验证hook点合法性
            if rule.get("target_hook") not in ALLOWED_HOOKS:
                logger.warning(f"Hook点不合法: {rule.get('target_hook')}")
                if attempt < max_retries - 1:
                    continue
                raise InvalidHookError(
                    f"Hook点 '{rule.get('target_hook')}' 不在允许列表中",
                    hook_name=rule.get("target_hook")
                )

            # 6. 生成唯一rule_id
            rule["rule_id"] = generate_rule_id()

            # 7. 验证代码格式
            try:
                ast.parse(rule["code"])
            except SyntaxError as e:
                logger.warning(f"代码语法错误: {str(e)}")
                if attempt < max_retries - 1:
                    continue
                raise InvalidObservationError(
                    f"生成的代码存在语法错误: {str(e)}",
                    observation_data={"code": rule["code"][:500]}
                )

            # 8. 验证规则格式
            is_valid, error_msg = validate_rule_format(rule)
            if not is_valid:
                logger.warning(f"规则格式验证失败: {error_msg}")
                if attempt < max_retries - 1:
                    continue
                raise InvalidObservationError(
                    f"规则格式无效: {error_msg}",
                    observation_data=rule
                )

            logger.info(f"规则生成成功: {rule['rule_id']}")
            return rule

        except (LLMServiceError, InvalidHookError, InvalidObservationError):
            raise
        except Exception as e:
            logger.error(f"规则生成异常: {str(e)}")
            if attempt < max_retries - 1:
                continue
            raise LLMServiceError(f"规则生成异常: {str(e)}")

    # 不应该到达这里
    raise LLMServiceError("规则生成失败，已达到最大重试次数")


def _build_generation_prompt(observation: Dict) -> str:
    """
    构造规则生成Prompt。

    Args:
        observation: 观察结论

    Returns:
        完整的prompt字符串
    """
    hook_interfaces = ""
    for hook_name, hook_spec in HOOK_SIGNATURES.items():
        params = ", ".join([f"{p['name']}: {p['type']}" for p in hook_spec["parameters"]])
        hook_interfaces += f"""
{hook_name}：{hook_spec.get('description', '')}
   接口：def {hook_spec['function_name']}({params}) -> {hook_spec['return_type']}
"""

    prompt = f"""你是一个Python代码生成专家。你的任务是根据观察结论生成优化规则。

【观察结论】
{json.dumps(observation, ensure_ascii=False, indent=2)}

【允许的Hook点】
{hook_interfaces}

请生成一个Python函数，输出JSON格式：
{{
  "rule_id": "自动生成，格式：rule_{{timestamp}}_{{random}}",
  "code": "完整的Python函数代码",
  "target_hook": "signal_detector/mood_detector/intervention_level",
  "description": "规则描述",
  "confidence": 0.85
}}

注意：
1. code必须是完整的、可执行的Python函数
2. 函数签名必须匹配target_hook的接口规范
3. 代码应简洁、高效，避免复杂逻辑
4. 必须包含类型注解和文档字符串
"""
    return prompt


def validate_rule(rule: Dict) -> Tuple[bool, str]:
    """
    对规则进行三关验证。

    Args:
        rule: generate_rule()返回的规则对象

    Returns:
        (是否通过, 原因说明)
    """
    logger.info(f"开始验证规则: {rule.get('rule_id', 'unknown')}")

    # 第一关：语法检查
    passed, reason = _validate_syntax(rule)
    if not passed:
        logger.warning(f"语法检查失败: {reason}")
        return False, reason

    logger.info("语法检查通过")

    # 第二关：签名校验
    passed, reason = _validate_signature(rule)
    if not passed:
        logger.warning(f"签名校验失败: {reason}")
        return False, reason

    logger.info("签名校验通过")

    # 第三关：子进程执行
    passed, reason = _validate_execution(rule)
    if not passed:
        logger.warning(f"子进程执行失败: {reason}")
        return False, reason

    logger.info("子进程执行通过")
    logger.info(f"规则验证通过: {rule.get('rule_id', 'unknown')}")
    return True, "验证通过"


def _validate_syntax(rule: Dict) -> Tuple[bool, str]:
    """
    第一关：语法检查。

    Args:
        rule: 规则对象

    Returns:
        (是否通过, 原因说明)
    """
    try:
        code = rule.get("code", "")
        if not code:
            return False, "代码为空"

        # 使用ast.parse()解析代码
        tree = ast.parse(code)

        # 检查AST根节点是否为FunctionDef
        if not isinstance(tree.body[0], ast.FunctionDef):
            return False, "代码必须是一个函数定义"

        return True, ""

    except SyntaxError as e:
        return False, f"语法错误: {str(e)}"
    except Exception as e:
        return False, f"语法检查异常: {str(e)}"


def _validate_signature(rule: Dict) -> Tuple[bool, str]:
    """
    第二关：签名校验。

    Args:
        rule: 规则对象

    Returns:
        (是否通过, 原因说明)
    """
    try:
        target_hook = rule.get("target_hook")
        if target_hook not in HOOK_SIGNATURES:
            return False, f"未知的Hook点: {target_hook}"

        hook_spec = HOOK_SIGNATURES[target_hook]

        # 解析代码获取函数定义
        tree = ast.parse(rule["code"])
        func_def = tree.body[0]

        # 检查函数名
        expected_func_name = hook_spec["function_name"]
        if func_def.name != expected_func_name:
            return False, f"函数名应为 '{expected_func_name}'，实际为 '{func_def.name}'"

        # 检查参数
        expected_params = hook_spec["parameters"]
        actual_args = func_def.args

        # 检查参数数量
        if len(actual_args.args) != len(expected_params):
            return False, f"参数数量不匹配，期望 {len(expected_params)} 个，实际 {len(actual_args.args)} 个"

        # 检查参数名称和类型注解
        for i, expected_param in enumerate(expected_params):
            actual_arg = actual_args.args[i]

            # 检查参数名称
            if actual_arg.arg != expected_param["name"]:
                return False, f"参数 {i+1} 名称应为 '{expected_param['name']}'，实际为 '{actual_arg.arg}'"

            # 检查类型注解
            if actual_arg.annotation:
                actual_type = ast.unparse(actual_arg.annotation)
                if actual_type != expected_param["type"]:
                    return False, f"参数 '{expected_param['name']}' 类型应为 '{expected_param['type']}'，实际为 '{actual_type}'"

        # 检查返回值类型注解
        if func_def.returns:
            actual_return = ast.unparse(func_def.returns)
            if actual_return != hook_spec["return_type"]:
                return False, f"返回值类型应为 '{hook_spec['return_type']}'，实际为 '{actual_return}'"

        return True, ""

    except Exception as e:
        return False, f"签名校验异常: {str(e)}"


def _validate_execution(rule: Dict) -> Tuple[bool, str]:
    """
    第三关：子进程执行。

    Args:
        rule: 规则对象

    Returns:
        (是否通过, 原因说明)
    """
    import subprocess
    import tempfile

    try:
        target_hook = rule.get("target_hook")
        code = rule.get("code", "")

        # 构造测试数据
        test_data = _build_test_data(target_hook)

        # 创建临时Python文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            # 写入代码
            f.write(code)
            f.write("\n\n")
            # 写入测试代码
            f.write(f"""
import json
import sys

# 测试数据
test_data = {json.dumps(test_data)}

# 获取函数名
func_name = "{HOOK_SIGNATURES[target_hook]['function_name']}"

# 执行函数
try:
    result = eval(func_name)(test_data)
    # 验证返回值格式
    required_fields = {HOOK_SIGNATURES[target_hook]['required_return_fields']}
    for field in required_fields:
        if field not in result:
            print(json.dumps({{"success": False, "error": f"返回值缺少字段: {{field}}"}}))
            sys.exit(1)

    print(json.dumps({{"success": True, "result": result}}))
except Exception as e:
    print(json.dumps({{"success": False, "error": str(e)}}))
    sys.exit(1)
""")
            temp_file = f.name

        # 在子进程中执行，设置10秒超时
        try:
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                text=True,
                timeout=10,
                encoding='utf-8'
            )

            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else "未知错误"
                return False, f"执行失败: {error_msg}"

            # 解析执行结果
            try:
                output = json.loads(result.stdout.strip())
                if not output.get("success"):
                    return False, f"执行失败: {output.get('error', '未知错误')}"
                return True, ""
            except json.JSONDecodeError:
                return False, f"执行结果格式错误: {result.stdout[:200]}"

        except subprocess.TimeoutExpired:
            # 清理临时文件
            try:
                os.unlink(temp_file)
            except:
                pass
            return False, "执行超时（10秒）"

    except Exception as e:
        return False, f"子进程执行异常: {str(e)}"


def _build_test_data(target_hook: str) -> Dict:
    """
    构造测试数据。

    Args:
        target_hook: 目标Hook点

    Returns:
        测试数据字典
    """
    if target_hook == "signal_detector":
        return {
            "user_state": {"mood": "neutral", "energy": 0.7},
            "event_history": [
                {"type": "task_completed", "timestamp": "2024-01-01T10:00:00Z"},
                {"type": "goal_created", "timestamp": "2024-01-01T11:00:00Z"}
            ],
            "baseline": {"avg_completion_rate": 0.8}
        }
    elif target_hook == "mood_detector":
        return {
            "recent_events": [
                {"type": "task_completed", "timestamp": "2024-01-01T10:00:00Z"},
                {"type": "feedback_positive", "timestamp": "2024-01-01T11:00:00Z"}
            ],
            "user_profile": {"occupation": "developer"},
            "time_context": {"hour": 14, "day_of_week": "Monday"}
        }
    elif target_hook == "intervention_level":
        return {
            "signal_info": {"signal_detected": True, "severity": 0.6},
            "mood_info": {"mood_detected": True, "intensity": 0.5},
            "user_preferences": {"intervention_frequency": "medium"}
        }
    else:
        return {}


def apply_rule(rule: Dict) -> bool:
    """
    应用通过验证的规则。

    Args:
        rule: 已通过验证的规则对象

    Returns:
        是否应用成功

    Raises:
        RuleNotValidatedError: 规则未通过验证
        FileWriteError: 文件写入失败
        ManifestUpdateError: manifest.json更新失败
    """
    logger.info(f"开始应用规则: {rule.get('rule_id', 'unknown')}")

    # 1. 验证规则状态（检查是否已通过验证）
    if not rule.get("validated", False):
        logger.error("规则未通过验证")
        raise RuleNotValidatedError(
            "规则必须通过验证才能应用",
            rule_id=rule.get("rule_id")
        )

    # 2. 确保目录存在
    try:
        RULES_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"确保规则目录存在: {RULES_DIR}")
    except Exception as e:
        logger.error(f"创建规则目录失败: {str(e)}")
        raise FileWriteError(f"创建规则目录失败: {str(e)}", file_path=str(RULES_DIR))

    rule_file_path = RULES_DIR / f"{rule['rule_id']}.py"

    # 3. 写入规则文件（使用原子写入）
    try:
        _write_rule_file(rule, rule_file_path)
        logger.info(f"规则文件写入成功: {rule_file_path}")
    except Exception as e:
        logger.error(f"规则文件写入失败: {str(e)}")
        raise FileWriteError(f"规则文件写入失败: {str(e)}", file_path=str(rule_file_path))

    # 4. 读取当前性能指标作为baseline
    performance_baseline = _get_performance_baseline(rule["target_hook"])
    logger.info(f"性能基线: {performance_baseline}")

    # 5. 加载manifest.json
    manifest = _load_manifest()

    # 6. 添加新规则元数据
    now = datetime.now()
    expires_at = now + timedelta(days=30)

    rule_metadata = {
        "rule_id": rule["rule_id"],
        "created_at": now.isoformat(),
        "target_hook": rule["target_hook"],
        "description": rule["description"],
        "confidence": rule["confidence"],
        "expires_at": expires_at.isoformat(),
        "status": "active",
        "performance_baseline": performance_baseline,
        "performance_current": performance_baseline,
        "rollback_info": None
    }

    manifest["rules"].append(rule_metadata)
    manifest["last_updated"] = now.isoformat()

    # 7. 写入manifest.json（使用文件锁和原子写入）
    try:
        _write_manifest(manifest)
        logger.info("manifest.json更新成功")
    except Exception as e:
        logger.error(f"manifest.json更新失败: {str(e)}")
        # 8. 失败时回滚已写入的规则文件
        try:
            if rule_file_path.exists():
                rule_file_path.unlink()
                logger.info("已回滚规则文件")
        except Exception as rollback_error:
            logger.error(f"回滚规则文件失败: {str(rollback_error)}")
        raise ManifestUpdateError(f"manifest.json更新失败: {str(e)}", manifest_path=str(MANIFEST_PATH))

    logger.info(f"规则应用成功: {rule['rule_id']}")
    return True


def _write_rule_file(rule: Dict, file_path: Path) -> None:
    """
    写入规则文件（原子写入）。

    Args:
        rule: 规则对象
        file_path: 文件路径
    """
    # 构造规则文件内容
    content = f'''"""
进化规则：{rule["rule_id"]}
创建时间：{datetime.now().isoformat()}
目标Hook：{rule["target_hook"]}
描述：{rule["description"]}
置信度：{rule["confidence"]}
"""

{rule["code"]}
'''

    # 原子写入：先写临时文件再重命名
    temp_path = file_path.with_suffix('.tmp')
    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            f.write(content)

        # 重命名临时文件（跨平台兼容）
        shutil.move(str(temp_path), str(file_path))

    except Exception as e:
        # 清理临时文件
        if temp_path.exists():
            temp_path.unlink()
        raise e


def _get_performance_baseline(target_hook: str) -> Dict:
    """
    读取当前性能指标作为baseline。

    Args:
        target_hook: 目标Hook点

    Returns:
        性能基线字典
    """
    # 默认性能基线
    default_baseline = {
        "accuracy": 0.75,
        "response_time": 1.0,
        "user_satisfaction": 0.8
    }

    try:
        from core.paths import DATA_DIR

        event_log_path = DATA_DIR / "event_log.jsonl"
        if not event_log_path.exists():
            return default_baseline

        # 读取最近7天的事件日志
        cutoff_date = datetime.now() - timedelta(days=7)
        events = []

        with open(event_log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    event = json.loads(line)
                    # 筛选与target_hook相关的事件
                    if event.get("type") == f"{target_hook}_triggered":
                        timestamp_str = event.get("timestamp", "")
                        if timestamp_str:
                            try:
                                event_time = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                                if event_time >= cutoff_date:
                                    events.append(event)
                            except ValueError:
                                continue
                except json.JSONDecodeError:
                    continue

        if not events:
            return default_baseline

        # 计算平均性能指标
        total_accuracy = 0
        total_response_time = 0
        total_satisfaction = 0
        count = 0

        for event in events:
            payload = event.get("payload", {})
            total_accuracy += payload.get("accuracy", 0.75)
            total_response_time += payload.get("response_time", 1.0)
            total_satisfaction += payload.get("user_satisfaction", 0.8)
            count += 1

        if count > 0:
            return {
                "accuracy": total_accuracy / count,
                "response_time": total_response_time / count,
                "user_satisfaction": total_satisfaction / count
            }
        else:
            return default_baseline

    except Exception as e:
        logger.warning(f"读取性能基线失败，使用默认值: {str(e)}")
        return default_baseline


def _load_manifest() -> Dict:
    """
    加载manifest.json。

    Returns:
        manifest字典
    """
    if not MANIFEST_PATH.exists():
        logger.info("manifest.json不存在，创建空结构")
        return {
            "version": "1.0",
            "last_updated": None,
            "rules": []
        }

    try:
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        # 验证manifest结构
        if "version" not in manifest:
            manifest["version"] = "1.0"
        if "last_updated" not in manifest:
            manifest["last_updated"] = None
        if "rules" not in manifest:
            manifest["rules"] = []

        return manifest

    except json.JSONDecodeError as e:
        logger.error(f"manifest.json格式错误: {str(e)}")
        # 备份损坏文件
        backup_path = MANIFEST_PATH.with_suffix('.json.backup')
        try:
            shutil.move(str(MANIFEST_PATH), str(backup_path))
            logger.info(f"已备份损坏的manifest.json到: {backup_path}")
        except Exception:
            pass

        # 创建新的manifest
        return {
            "version": "1.0",
            "last_updated": None,
            "rules": []
        }

    except Exception as e:
        logger.error(f"读取manifest.json失败: {str(e)}")
        raise ManifestUpdateError(f"读取manifest.json失败: {str(e)}", manifest_path=str(MANIFEST_PATH))


def _write_manifest(manifest: Dict) -> None:
    """
    写入manifest.json（使用文件锁和原子写入）。

    Args:
        manifest: manifest字典
    """
    # 原子写入：先写临时文件再重命名
    temp_path = MANIFEST_PATH.with_suffix('.json.tmp')

    try:
        with open(temp_path, 'w', encoding='utf-8') as f:
            # 尝试获取文件锁（仅Unix系统）
            if os.name != 'nt':
                try:
                    import fcntl
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except Exception:
                    pass

            json.dump(manifest, f, ensure_ascii=False, indent=2)

        # 重命名临时文件（跨平台兼容）
        shutil.move(str(temp_path), str(MANIFEST_PATH))

    except Exception as e:
        # 清理临时文件
        if temp_path.exists():
            temp_path.unlink()
        raise e
