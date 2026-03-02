"""
Verification script for Phase 2: Core Logic.
Tests GoalGenerator, TaskDecomposer, and TaskDispatcher.
"""
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from datetime import date, datetime
from unittest.mock import MagicMock
from core.models import UserProfile, Goal, Task, TaskStatus
from core.goal_generator import GoalGenerator
from core.task_decomposer import TaskDecomposer
from core.task_dispatcher import TaskDispatcher
from core.blueprint import Blueprint
from core.llm_adapter import LLMResponse

def mock_llm_generate(prompt: str, **kwargs):
    """Mock LLM response based on prompt content"""
    if "candidate goals" in prompt:
        return LLMResponse(
            model="mock",
            content="""
            [
                {
                    "id": "mock1",
                    "title": "Learn PyTorch",
                    "description": "Deep Learning basics",
                    "resource_description": "Official Docs",
                    "target_level": "Basic"
                },
                {
                    "id": "mock2",
                    "title": "Run 5km",
                    "description": "Physical health",
                    "resource_description": "Park",
                    "target_level": "Fit"
                }
            ]
            """
        )
    elif "Decompose" in prompt:
        return LLMResponse(
            model="mock",
            content="""
            [
                {
                    "description": "Install PyTorch",
                    "minutes": 30,
                    "time_of_day": "Morning"
                },
                {
                    "description": "Tensors Tutorial",
                    "minutes": 60,
                    "time_of_day": "Evening"
                }
            ]
            """
        )
    return LLMResponse(error="Unknown prompt", model="mock", content="")

def test_goal_generator():
    print("\n--- Testing GoalGenerator ---")
    bp = Blueprint()
    gen = GoalGenerator(bp)
    
    # Mock LLM
    gen.llm = MagicMock()
    gen.llm.generate.side_effect = mock_llm_generate
    
    profile = UserProfile(occupation="Coder", daily_hours="3h")
    candidates = gen.generate_candidates(profile)
    
    print(f"Generated {len(candidates)} candidates.")
    for g, s in candidates:
        print(f"  - [{g.id}] {g.title} (Score: {s.score:.2f})")
        
    assert len(candidates) > 0
    assert candidates[0][0].title == "Learn PyTorch"

def test_task_decomposer():
    print("\n--- Testing TaskDecomposer ---")
    decomp = TaskDecomposer()
    decomp.llm = MagicMock()
    decomp.llm.generate.side_effect = mock_llm_generate
    
    goal = Goal(id="g1", title="Learn PyTorch", description="", source="ai", status="active")
    tasks = decomp.decompose_goal(goal, start_date=date.today())
    
    print(f"Decomposed into {len(tasks)} tasks:")
    for t in tasks:
        print(f"  - {t.scheduled_date} [{t.scheduled_time}] {t.description}")
        
    assert len(tasks) == 2
    assert tasks[0].description == "Install PyTorch"

def test_task_dispatcher():
    print("\n--- Testing TaskDispatcher ---")
    disp = TaskDispatcher()
    
    t1 = Task(id="1", goal_id="g", description="Old Task", scheduled_date=date(2025, 1, 1), status=TaskStatus.PENDING)
    t2 = Task(id="2", goal_id="g", description="Future Task", scheduled_date=date(2099, 1, 1), status=TaskStatus.PENDING)
    t3 = Task(id="3", goal_id="g", description="Today Morning", scheduled_date=date.today(), scheduled_time="09:00", status=TaskStatus.PENDING)
    t4 = Task(id="4", goal_id="g", description="Today Evening", scheduled_date=date.today(), scheduled_time="20:00", status=TaskStatus.PENDING)
    
    # Test 1: Should pick Old Task (expired)
    current = disp.get_current_task([t1, t2, t3, t4])
    print(f"Selected: {current.description} (Expected: Old Task)")
    assert current.id == "1"
    
    # Test 2: Mark old as completed, should pick Today Morning
    t1.status = TaskStatus.COMPLETED
    current = disp.get_current_task([t1, t2, t3, t4])
    print(f"Selected: {current.description} (Expected: Today Morning)")
    assert current.id == "3"
    
    print("Dispatcher logic check passed.")

if __name__ == "__main__":
    try:
        test_goal_generator()
        test_task_decomposer()
        test_task_dispatcher()
        print("\n✅ Phase 2 Verification SUCCESS!")
    except Exception as e:
        print(f"\n❌ Phase 2 Verification FAILED: {e}")
        import traceback
        traceback.print_exc()
