"""
Audit Logger for AI Life OS.

Records all AI decisions with complete reasoning chain.
Supports querying historical decisions and generating reports.
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict


# 审计日志目录
DATA_DIR = Path(__file__).parent.parent / "data"
AUDIT_LOG_PATH = DATA_DIR / "audit_log.jsonl"


@dataclass
class AuditEntry:
    """A single audit log entry."""
    timestamp: str
    decision_type: str  # planning, execution, failure_handling
    action_id: str
    reasoning: Dict[str, Any]  # trigger, constraint, risk
    state_snapshot: Dict[str, Any]  # relevant state at decision time
    outcome: Optional[str] = None  # success, failure, pending
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def log_decision(
    decision_type: str,
    action_id: str,
    reasoning: Dict[str, Any],
    state_snapshot: Optional[Dict[str, Any]] = None
) -> AuditEntry:
    """
    Log an AI decision to the audit log.
    
    Args:
        decision_type: Type of decision (planning, execution, etc.)
        action_id: ID of the action being decided
        reasoning: Decision reasoning (trigger, constraint, risk)
        state_snapshot: Relevant state at decision time
    
    Returns:
        The created AuditEntry.
    """
    entry = AuditEntry(
        timestamp=datetime.now().isoformat(),
        decision_type=decision_type,
        action_id=action_id,
        reasoning=reasoning,
        state_snapshot=state_snapshot or {}
    )
    
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    
    return entry


def update_outcome(action_id: str, outcome: str) -> bool:
    """
    Update the outcome of a logged decision.
    
    Note: This is a simplified implementation that appends a new entry.
    A production system would update in place.
    
    Returns:
        True if update was logged.
    """
    entry = {
        "timestamp": datetime.now().isoformat(),
        "type": "outcome_update",
        "action_id": action_id,
        "outcome": outcome
    }
    
    with open(AUDIT_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    return True


def query_decisions(
    decision_type: Optional[str] = None,
    action_id: Optional[str] = None,
    limit: int = 100
) -> List[Dict[str, Any]]:
    """
    Query historical decisions from the audit log.
    
    Args:
        decision_type: Filter by decision type
        action_id: Filter by action ID
        limit: Maximum number of results (default: 100, 经验值)
    
    Returns:
        List of matching audit entries.
    """
    if not AUDIT_LOG_PATH.exists():
        return []
    
    results = []
    
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                
                # 跳过 outcome_update 条目
                if entry.get("type") == "outcome_update":
                    continue
                
                # 应用过滤器
                if decision_type and entry.get("decision_type") != decision_type:
                    continue
                if action_id and entry.get("action_id") != action_id:
                    continue
                
                results.append(entry)
                
            except json.JSONDecodeError:
                continue
    
    # 返回最近的条目
    return results[-limit:]


def get_decision_chain(action_id: str) -> List[Dict[str, Any]]:
    """
    Get the complete decision chain for an action.
    
    Returns all audit entries related to a specific action,
    including planning, execution, and outcome updates.
    """
    if not AUDIT_LOG_PATH.exists():
        return []
    
    chain = []
    
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if entry.get("action_id") == action_id:
                    chain.append(entry)
            except json.JSONDecodeError:
                continue
    
    return chain


def generate_audit_report(days: int = 7) -> Dict[str, Any]:
    """
    Generate an audit report for the specified period.
    
    Args:
        days: Number of days to include
    
    Returns:
        Report with decision statistics and patterns.
    """
    from datetime import timedelta
    
    cutoff = datetime.now() - timedelta(days=days)
    
    if not AUDIT_LOG_PATH.exists():
        return {"total_decisions": 0, "by_type": {}}
    
    decisions_by_type: Dict[str, int] = {}
    total = 0
    
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                
                if entry.get("type") == "outcome_update":
                    continue
                
                timestamp_str = entry.get("timestamp", "")
                if timestamp_str:
                    entry_time = datetime.fromisoformat(timestamp_str)
                    if entry_time < cutoff:
                        continue
                
                decision_type = entry.get("decision_type", "unknown")
                decisions_by_type[decision_type] = decisions_by_type.get(decision_type, 0) + 1
                total += 1
                
            except (json.JSONDecodeError, ValueError):
                continue
    
    return {
        "period_days": days,
        "generated_at": datetime.now().isoformat(),
        "total_decisions": total,
        "by_type": decisions_by_type
    }


def clear_old_audit_logs(retention_days: int = 90) -> int:
    """
    Clear audit logs older than retention period.
    
    Args:
        retention_days: Days to retain (default: 90, 经验值)
    
    Returns:
        Number of entries removed.
    """
    if not AUDIT_LOG_PATH.exists():
        return 0
    
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=retention_days)
    
    # 读取所有条目
    entries = []
    removed = 0
    
    with open(AUDIT_LOG_PATH, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                timestamp_str = entry.get("timestamp", "")
                if timestamp_str:
                    entry_time = datetime.fromisoformat(timestamp_str)
                    if entry_time >= cutoff:
                        entries.append(line)
                    else:
                        removed += 1
                else:
                    entries.append(line)
            except (json.JSONDecodeError, ValueError):
                continue
    
    # 重写文件
    with open(AUDIT_LOG_PATH, "w", encoding="utf-8") as f:
        for entry in entries:
            f.write(entry + "\n")
    
    return removed
