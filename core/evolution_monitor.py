"""
自我进化引擎效果监控模块。

该模块负责监控已上线规则的效果，并在效果不佳时自动回滚。

主要功能：
- evaluate_rules(): 评估所有已上线规则的效果
- rollback_rule(): 回滚指定规则
"""
import json
import os
import logging
import shutil
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from pathlib import Path

from core.exceptions import AILifeError
from core.logger import get_logger


# ========== 异常定义 ==========

class MonitorError(AILifeError):
    """监控模块基础异常。"""

    def __init__(self, message: str, hint: Optional[str] = None):
        super().__init__(message, hint)


class RuleNotFoundError(MonitorError):
    """规则不存在。"""

    def __init__(self, message: str, rule_id: Optional[str] = None):
        hint = f"规则 '{rule_id}' 不存在" if rule_id else "规则不存在"
        super().__init__(message, hint)
        self.rule_id = rule_id


class RollbackFailedError(MonitorError):
    """回滚操作失败。"""

    def __init__(self, message: str, rule_id: Optional[str] = None):
        hint = "回滚操作失败，需要人工介入"
        super().__init__(message, hint)
        self.rule_id = rule_id


# ========== 常量定义 ==========

# 规则存储路径
RULES_DIR = Path(__file__).parent.parent / "skills" / "evolved"
MANIFEST_PATH = RULES_DIR / "manifest.json"

# 评估参数
EVALUATION_PERIOD_DAYS = 7  # 评估周期：7天
ROLLBACK_THRESHOLD = -0.1  # 回滚阈值：下降10%
MIN_SAMPLE_SIZE = 10  # 最小样本数


# ========== 日志配置 ==========

logger = get_logger("evolution_monitor")


# ========== 主函数 ==========

def evaluate_rules() -> List[Dict]:
    """
    评估所有已上线规则的效果。

    Returns:
        评估结果列表，每项包含rule_id、performance_delta、should_rollback
    """
    logger.info("开始评估规则效果")

    # 1. 读取manifest.json
    manifest = _load_manifest()
    if not manifest or not manifest.get("rules"):
        logger.info("没有规则需要评估")
        return []

    # 2. 过滤规则：只评估status为"active"且已上线≥7天的规则
    now = datetime.now()
    cutoff_date = now - timedelta(days=EVALUATION_PERIOD_DAYS)

    active_rules = []
    for rule in manifest["rules"]:
        if rule.get("status") != "active":
            continue

        created_at_str = rule.get("created_at")
        if not created_at_str:
            continue

        try:
            created_at = datetime.fromisoformat(created_at_str)
            if created_at <= cutoff_date:
                active_rules.append(rule)
        except ValueError:
            logger.warning(f"规则 {rule.get('rule_id')} 的时间格式错误")
            continue

    logger.info(f"找到 {len(active_rules)} 条需要评估的规则")

    # 3. 对每条规则执行评估
    results = []
    for rule in active_rules:
        try:
            result = _evaluate_single_rule(rule)
            if result:
                results.append(result)
        except Exception as e:
            logger.error(f"评估规则 {rule.get('rule_id')} 失败: {str(e)}")
            continue

    logger.info(f"评估完成，共 {len(results)} 条规则")
    return results


def rollback_rule(rule_id: str) -> bool:
    """
    回滚指定规则。

    Args:
        rule_id: 要回滚的规则ID

    Returns:
        是否回滚成功

    Raises:
        RuleNotFoundError: 规则不存在
        RollbackFailedError: 回滚操作失败
    """
    logger.info(f"开始回滚规则: {rule_id}")

    # 1. 验证规则存在
    manifest = _load_manifest()
    rule = None
    rule_index = -1

    for i, r in enumerate(manifest.get("rules", [])):
        if r.get("rule_id") == rule_id:
            rule = r
            rule_index = i
            break

    if not rule:
        logger.error(f"规则不存在: {rule_id}")
        raise RuleNotFoundError(f"规则不存在: {rule_id}", rule_id=rule_id)

    # 2. 删除规则文件
    rule_file_path = RULES_DIR / f"{rule_id}.py"
    if rule_file_path.exists():
        try:
            rule_file_path.unlink()
            logger.info(f"已删除规则文件: {rule_file_path}")
        except Exception as e:
            logger.warning(f"删除规则文件失败: {str(e)}")
    else:
        logger.warning(f"规则文件不存在: {rule_file_path}")

    # 3. 更新manifest.json
    try:
        manifest["rules"][rule_index]["status"] = "rolled_back"
        manifest["rules"][rule_index]["rollback_info"] = {
            "timestamp": datetime.now().isoformat(),
            "reason": "性能下降超过阈值",
            "performance_delta": rule.get("performance_current", {}).get("delta", 0)
        }
        manifest["last_updated"] = datetime.now().isoformat()

        _write_manifest(manifest)
        logger.info("manifest.json更新成功")
    except Exception as e:
        logger.error(f"更新manifest.json失败: {str(e)}")
        # 标记为rollback_failed
        try:
            manifest["rules"][rule_index]["status"] = "rollback_failed"
            manifest["rules"][rule_index]["rollback_info"] = {
                "timestamp": datetime.now().isoformat(),
                "reason": f"回滚失败: {str(e)}"
            }
            _write_manifest(manifest)
        except Exception:
            pass
        raise RollbackFailedError(f"更新manifest.json失败: {str(e)}", rule_id=rule_id)

    # 4. 写入回滚事件到事件日志
    try:
        _write_rollback_event(rule)
        logger.info("回滚事件已写入事件日志")
    except Exception as e:
        logger.warning(f"写入回滚事件失败: {str(e)}")

    logger.info(f"规则回滚成功: {rule_id}")
    return True


# ========== 辅助函数 ==========

def _load_manifest() -> Dict:
    """
    加载manifest.json。

    Returns:
        manifest字典
    """
    if not MANIFEST_PATH.exists():
        return {"version": "1.0", "last_updated": None, "rules": []}

    try:
        with open(MANIFEST_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"加载manifest.json失败: {str(e)}")
        return {"version": "1.0", "last_updated": None, "rules": []}


def _write_manifest(manifest: Dict) -> None:
    """
    写入manifest.json。

    Args:
        manifest: manifest字典
    """
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

        shutil.move(str(temp_path), str(MANIFEST_PATH))

    except Exception as e:
        if temp_path.exists():
            temp_path.unlink()
        raise e


def _evaluate_single_rule(rule: Dict) -> Optional[Dict]:
    """
    评估单条规则。

    Args:
        rule: 规则元数据

    Returns:
        评估结果字典，或None（如果评估失败）
    """
    rule_id = rule.get("rule_id")
    target_hook = rule.get("target_hook")
    created_at_str = rule.get("created_at")

    if not all([rule_id, target_hook, created_at_str]):
        logger.warning(f"规则 {rule_id} 缺少必要字段")
        return None

    try:
        created_at = datetime.fromisoformat(created_at_str)
    except ValueError:
        logger.warning(f"规则 {rule_id} 时间格式错误")
        return None

    # 获取上线前7天和上线后7天的指标
    baseline = rule.get("performance_baseline", {})
    current = _get_current_performance(target_hook, created_at)

    if not baseline or not current:
        logger.warning(f"规则 {rule_id} 数据不足，跳过评估")
        return None

    # 计算performance_delta
    delta = _calculate_performance_delta(baseline, current)

    # 判断是否需要回滚
    should_rollback = delta < ROLLBACK_THRESHOLD

    logger.info(
        f"规则 {rule_id}: delta={delta:.3f}, "
        f"should_rollback={should_rollback}"
    )

    return {
        "rule_id": rule_id,
        "performance_delta": delta,
        "should_rollback": should_rollback
    }


def _get_current_performance(target_hook: str, created_at: datetime) -> Optional[Dict]:
    """
    获取规则上线后的性能指标。

    Args:
        target_hook: 目标Hook点
        created_at: 规则创建时间

    Returns:
        性能指标字典，或None（如果数据不足）
    """
    from core.paths import DATA_DIR

    event_log_path = DATA_DIR / "event_log.jsonl"
    if not event_log_path.exists():
        return None

    # 读取上线后7天的事件日志
    end_date = created_at + timedelta(days=EVALUATION_PERIOD_DAYS)
    now = datetime.now()

    # 如果还未满7天，使用当前时间作为结束时间
    if end_date > now:
        end_date = now

    events = []
    try:
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
                                event_time = datetime.fromisoformat(
                                    timestamp_str.replace("Z", "+00:00")
                                )
                                if created_at <= event_time <= end_date:
                                    events.append(event)
                            except ValueError:
                                continue
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        logger.error(f"读取事件日志失败: {str(e)}")
        return None

    # 检查样本数
    if len(events) < MIN_SAMPLE_SIZE:
        logger.warning(f"样本数不足: {len(events)} < {MIN_SAMPLE_SIZE}")
        return None

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
        return None


def _calculate_performance_delta(baseline: Dict, current: Dict) -> float:
    """
    计算性能变化值。

    Args:
        baseline: 基线性能
        current: 当前性能

    Returns:
        性能变化值（正数表示提升，负数表示下降）
    """
    # 使用加权平均计算综合性能
    weights = {
        "accuracy": 0.4,
        "response_time": 0.3,  # 响应时间越低越好，需要反转
        "user_satisfaction": 0.3
    }

    baseline_score = (
        baseline.get("accuracy", 0.75) * weights["accuracy"] +
        (1 - baseline.get("response_time", 1.0) / 2) * weights["response_time"] +
        baseline.get("user_satisfaction", 0.8) * weights["user_satisfaction"]
    )

    current_score = (
        current.get("accuracy", 0.75) * weights["accuracy"] +
        (1 - current.get("response_time", 1.0) / 2) * weights["response_time"] +
        current.get("user_satisfaction", 0.8) * weights["user_satisfaction"]
    )

    # 计算变化百分比
    if baseline_score > 0:
        delta = (current_score - baseline_score) / baseline_score
    else:
        delta = 0

    return delta


def _write_rollback_event(rule: Dict) -> None:
    """
    写入回滚事件到事件日志。

    Args:
        rule: 规则元数据
    """
    from core.paths import DATA_DIR
    from core.event_sourcing import append_event

    event = {
        "type": "evolution_rollback",
        "timestamp": datetime.now().isoformat(),
        "payload": {
            "rule_id": rule.get("rule_id"),
            "reason": "性能下降超过阈值",
            "performance_delta": rule.get("performance_current", {}).get("delta", 0),
            "baseline": rule.get("performance_baseline", {}),
            "current": rule.get("performance_current", {})
        }
    }

    try:
        # 使用event_sourcing的append_event函数
        append_event(event)
    except Exception as e:
        # 如果append_event失败，直接写入文件
        event_log_path = DATA_DIR / "event_log.jsonl"
        try:
            with open(event_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(event, ensure_ascii=False) + "\n")
        except Exception as write_error:
            logger.error(f"写入回滚事件失败: {str(write_error)}")
            raise e
