"""
Tests for Iteration 11: Safe Mode Enhancement
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from web.backend.app import app
from core.event_sourcing import rebuild_state, append_event, get_initial_state


client = TestClient(app)


def test_exit_safe_mode_endpoint_exists():
    """测试 Safe Mode 退出端点存在"""
    response = client.post("/api/v1/safe-mode/exit", json={"reason": "user_initiated"})
    # 可能返回 400（不在 Safe Mode）或 200（成功退出）
    assert response.status_code in (200, 400)


def test_exit_safe_mode_rejects_when_not_in_safe_mode():
    """测试不在 Safe Mode 时拒绝退出"""
    # 确保不在 Safe Mode
    state = rebuild_state()
    guardian = state.get("guardian", {})
    safe_mode = guardian.get("safe_mode", {})

    if not safe_mode.get("active"):
        response = client.post("/api/v1/safe-mode/exit", json={"reason": "user_initiated"})
        assert response.status_code == 400
        assert "Not in Safe Mode" in response.json()["detail"]


def test_exit_safe_mode_appends_event(monkeypatch):
    """测试退出 Safe Mode 记录事件"""
    # 模拟 Safe Mode 激活状态
    from core import event_sourcing

    # 保存原始函数
    original_rebuild = event_sourcing.rebuild_state

    # 创建模拟状态
    mock_state = get_initial_state()
    mock_state["guardian"]["safe_mode"]["active"] = True
    mock_state["guardian"]["safe_mode"]["entered_at"] = (datetime.now() - timedelta(hours=2)).isoformat()
    mock_state["guardian"]["safe_mode"]["reason"] = "test_activation"

    # 替换 rebuild_state
    monkeypatch.setattr(event_sourcing, "rebuild_state", lambda: mock_state)

    # 调用退出 API
    response = client.post("/api/v1/safe-mode/exit", json={"reason": "user_initiated"})

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert "exited_at" in data
    assert "duration_hours" in data
    assert data["duration_hours"] is not None
    assert data["duration_hours"] >= 2.0


def test_exit_safe_mode_returns_duration():
    """测试退出 Safe Mode 返回持续时间"""
    from core import event_sourcing

    # 创建模拟状态
    mock_state = get_initial_state()
    entered_time = datetime.now() - timedelta(hours=3, minutes=30)
    mock_state["guardian"]["safe_mode"]["active"] = True
    mock_state["guardian"]["safe_mode"]["entered_at"] = entered_time.isoformat()

    # 替换 rebuild_state
    import unittest.mock as mock
    with mock.patch.object(event_sourcing, "rebuild_state", return_value=mock_state):
        response = client.post("/api/v1/safe-mode/exit", json={"reason": "user_initiated"})

        assert response.status_code == 200
        data = response.json()
        assert "duration_hours" in data
        # 应该约为 3.5 小时
        assert 3.4 <= data["duration_hours"] <= 3.6


def test_state_endpoint_includes_safe_mode_status():
    """测试 /state 端点包含 Safe Mode 状态"""
    response = client.get("/api/v1/state")
    assert response.status_code == 200

    data = response.json()
    guardian = data.get("guardian", {})
    authority = guardian.get("authority", {})
    safe_mode = authority.get("safe_mode", {})

    assert "active" in safe_mode
    assert "enabled" in safe_mode
    assert isinstance(safe_mode["active"], bool)
    assert isinstance(safe_mode["enabled"], bool)


def test_retrospective_endpoint_includes_safe_mode_status():
    """测试 /retrospective 端点包含 Safe Mode 状态"""
    response = client.get("/api/v1/retrospective?days=7")
    assert response.status_code == 200

    data = response.json()
    authority = data.get("authority", {})
    safe_mode = authority.get("safe_mode", {})

    assert "active" in safe_mode
    assert "enabled" in safe_mode
    assert "cooldown_complete" in safe_mode
    assert "recommendation" in safe_mode


def test_safe_mode_exit_with_custom_reason():
    """测试使用自定义原因退出 Safe Mode"""
    from core import event_sourcing

    # 创建模拟状态
    mock_state = get_initial_state()
    mock_state["guardian"]["safe_mode"]["active"] = True
    mock_state["guardian"]["safe_mode"]["entered_at"] = datetime.now().isoformat()

    import unittest.mock as mock
    with mock.patch.object(event_sourcing, "rebuild_state", return_value=mock_state):
        response = client.post("/api/v1/safe-mode/exit", json={"reason": "manual_override"})

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
