"""
Unit tests for RuleEvaluator.
"""
import pytest
import tempfile
import yaml
from pathlib import Path


@pytest.fixture
def temp_rules_file():
    """创建临时规则文件用于测试。"""
    rules = {
        "version": 1,
        "hot_reload": False,  # 测试中禁用热加载
        "phases": {
            "deep_work": {
                "allow": ["flourishing_session", "maintenance"],
                "block": ["substrate_task"],
                "exceptions": {
                    "emergency_keywords": ["紧急", "CRITICAL"]
                }
            },
            "logistics": {
                "allow": "all"
            },
            "activation": {
                "allow": ["maintenance"],
                "block": "all_except_allowed"
            }
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
        yaml.dump(rules, f, allow_unicode=True)
        return Path(f.name)


@pytest.fixture
def rule_evaluator(temp_rules_file):
    """创建使用临时配置的 RuleEvaluator 实例。"""
    # 重置单例
    from core.rule_evaluator import RuleEvaluator
    RuleEvaluator._instance = None
    
    # 创建新实例并注入配置路径
    evaluator = RuleEvaluator()
    evaluator._config_path = temp_rules_file
    evaluator._load_rules()
    
    return evaluator


class TestRuleEvaluator:
    """RuleEvaluator 单元测试。"""
    
    def test_filter_deep_work_allows_l2(self, rule_evaluator):
        """深度工作期应允许 L2 (flourishing_session) 任务。"""
        actions = [
            {"id": "a1", "priority": "flourishing_session", "description": "深度学习"},
            {"id": "a2", "priority": "substrate_task", "description": "回复邮件"},
            {"id": "a3", "priority": "maintenance", "description": "系统备份"}
        ]
        
        filtered = rule_evaluator.filter_actions("deep_work", actions)
        
        assert len(filtered) == 2
        assert all(a["priority"] in ["flourishing_session", "maintenance"] for a in filtered)
    
    def test_filter_deep_work_emergency_bypass(self, rule_evaluator):
        """深度工作期应允许紧急任务绕过过滤。"""
        actions = [
            {"id": "a1", "priority": "substrate_task", "description": "服务器紧急宕机"},
        ]
        
        filtered = rule_evaluator.filter_actions("deep_work", actions)
        
        assert len(filtered) == 1
        assert filtered[0]["id"] == "a1"
    
    def test_filter_logistics_allows_all(self, rule_evaluator):
        """事务处理期应允许全部任务。"""
        actions = [
            {"id": "a1", "priority": "flourishing_session", "description": "深度学习"},
            {"id": "a2", "priority": "substrate_task", "description": "回复邮件"},
        ]
        
        filtered = rule_evaluator.filter_actions("logistics", actions)
        
        assert len(filtered) == 2
    
    def test_filter_activation_only_maintenance(self, rule_evaluator):
        """唤醒期应仅允许维护任务。"""
        actions = [
            {"id": "a1", "priority": "flourishing_session", "description": "深度学习"},
            {"id": "a2", "priority": "maintenance", "description": "晨间例行"},
        ]
        
        filtered = rule_evaluator.filter_actions("activation", actions)
        
        assert len(filtered) == 1
        assert filtered[0]["priority"] == "maintenance"
    
    def test_fallback_when_no_rules(self, rule_evaluator):
        """无规则时应全部通过。"""
        # 清空规则
        rule_evaluator._rules = {}
        
        actions = [
            {"id": "a1", "priority": "substrate_task", "description": "任务1"},
        ]
        
        filtered = rule_evaluator.filter_actions("unknown_phase", actions)
        
        assert len(filtered) == 1
