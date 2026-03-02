import pytest
from core.goal_decomposer import Goal, GoalType

def test_goal_type_compatibility():
    """Test backward compatibility for string inputs in GoalType."""
    # Case 1: Enum member
    g1 = Goal(id="1", title="T", description="D", created_at="now", type=GoalType.SUBSTRATE)
    assert g1.type == GoalType.SUBSTRATE
    
    # Case 2: String "substrate"
    g2 = Goal(id="2", title="T", description="D", created_at="now", type="substrate")
    assert g2.type == GoalType.SUBSTRATE
    
    # Case 3: String "L1_SUBSTRATE"
    g3 = Goal(id="3", title="T", description="D", created_at="now", type="L1_SUBSTRATE")
    assert g3.type == GoalType.SUBSTRATE

    # Case 4: String "flourishing"
    g4 = Goal(id="4", title="T", description="D", created_at="now", type="flourishing")
    assert g4.type == GoalType.FLOURISHING
    
    # Case 5: String "L2_FLOURISHING"
    g5 = Goal(id="5", title="T", description="D", created_at="now", type="L2_FLOURISHING")
    assert g5.type == GoalType.FLOURISHING
    
    # Case 6: Unknown string fallback
    g6 = Goal(id="6", title="T", description="D", created_at="now", type="unknown")
    assert g6.type == GoalType.SUBSTRATE
