import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../')))

from core.objective_engine.registry import GoalRegistry
from core.objective_engine.models import ObjectiveNode, GoalState, GoalLayer, GoalSource

def seed_demo_data():
    print("正在注入演示数据...")
    registry = GoalRegistry()

    # 1. 注入 Vision (愿景)
    vision_id = "vis_demo_001"
    if not any(v.id == vision_id for v in registry.visions):
        vision = ObjectiveNode(
            id=vision_id,
            title="成为 Eudaimonia 架构师",
            description="构建能促进人类繁荣的智能系统",
            layer=GoalLayer.VISION,
            state=GoalState.ACTIVE,
            source=GoalSource.USER_INPUT
        )
        registry.add_node(vision)
        print(f"✅ 已添加 Vision: {vision.title}")

    # 2. 注入 Pending Goal (待确认目标 - 模拟 Steward 推导)
    pending_id = "goal_demo_pending"
    if not any(g.id == pending_id for g in registry.goals + registry.objectives):
        pending_goal = ObjectiveNode(
            id=pending_id,
            title="阅读《尼各马可伦理学》",
            description="Steward: 为了理解'幸福'的定义，建议阅读经典原著。",
            layer=GoalLayer.GOAL,
            state=GoalState.VISION_PENDING_CONFIRMATION,
            source=GoalSource.SYSTEM,
            parent_id=vision_id
        )
        registry.add_node(pending_goal)
        print(f"✅ 已添加待确认目标: {pending_goal.title}")

    # 3. 注入 Active Goal (活跃目标 - 用于测试反馈)
    active_id = "goal_demo_active"
    if not any(g.id == active_id for g in registry.goals):
        active_goal = ObjectiveNode(
            id=active_id,
            title="重构 UI 交互层",
            description="测试自由文本反馈功能",
            layer=GoalLayer.GOAL,
            state=GoalState.ACTIVE,
            source=GoalSource.USER_INPUT,
            deadline="2026-01-30"
        )
        registry.add_node(active_goal)
        print(f"✅ 已添加活跃目标: {active_goal.title}")

    print("\n数据注入完成！请刷新 Web 页面查看。")

if __name__ == "__main__":
    seed_demo_data()
