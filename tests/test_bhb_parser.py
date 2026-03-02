import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
from core.strategic_engine.bhb_parser import parse_bhb, BHBConfig, LifeMetric

MOCK_BHB_CONTENT = """
# Better Human Blueprint

**"Empower the user to become their best self."**

### Goal 1: Financial Independence
### Goal 2: Physical Vitality

**Life Metric**: **Flow State Duration (hours/day)**
**Life Metric**: **Deep Conversations (count/week)**

**Phase 1: Activation**
**Phase 2: Deep Work**

**The Problem**: Distraction from social media
"""

@patch("core.strategic_engine.bhb_parser.BHB_PATH")
def test_parse_bhb(mock_path):
    # Mock existence and content
    mock_path.exists.return_value = True
    mock_path.read_text.return_value = MOCK_BHB_CONTENT
    
    config = parse_bhb()
    
    assert isinstance(config, BHBConfig)
    assert config.philosophy == "Empower the user to become their best self."
    assert "Financial Independence" in config.strategic_goals[0]
    assert len(config.life_metrics) == 2
    assert config.life_metrics[0].name == "flow_state_duration"
    assert config.energy_phases[0] == "Activation"
    assert "Distraction" in config.anti_patterns[0]

@patch("core.strategic_engine.bhb_parser.BHB_PATH")
def test_parse_bhb_missing_file(mock_path):
    mock_path.exists.return_value = False
    
    config = parse_bhb()
    assert config.philosophy == ""
    assert config.strategic_goals == []
