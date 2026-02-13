from typing import List
from datetime import datetime

from core.llm_adapter import get_llm
from core.utils import load_prompt, parse_llm_json
from core.objective_engine.models import GoalLayer, ObjectiveNode, GoalSource

def decompose_vision(
    vision_title: str,
    vision_description: str,
    timeframe: str = "18 months",
) -> List[ObjectiveNode]:
    """
    Decompose a Vision into Objectives and initial Goals.
    """
    llm = get_llm("strategic_brain")
    system_prompt = load_prompt("milestone_planning")

    if not system_prompt:
        system_prompt = "You are a strategic planner."

    prompt = f"""Vision: {vision_title}
Description: {vision_description}
Timeframe: {timeframe}

Please break this down into Quarterly Objectives and initial Goals.
Output JSON format:
```json
{{
  "objectives": [
    {{
      "title": "Objective Title",
      "description": "Objective Description",
      "deadline": "YYYY-MM-DD",
      "goals": [
        {{
          "title": "Goal Title",
          "description": "Goal Description",
          "deadline": "YYYY-MM-DD"
        }}
      ]
    }}
  ]
}}
```"""

    response = llm.generate(prompt, system_prompt=system_prompt)

    nodes = []
    if response.success and response.content:
        data = parse_llm_json(response.content)
        if data and "objectives" in data:
            for obj_data in data["objectives"]:
                # Create Objective Node
                obj_id = f"obj_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(nodes)}"
                obj_node = ObjectiveNode(
                    id=obj_id,
                    title=obj_data.get("title", "Unnamed Objective"),
                    description=obj_data.get("description", ""),
                    layer=GoalLayer.OBJECTIVE,
                    source=GoalSource.TOP_DOWN,
                    deadline=obj_data.get("deadline")
                )
                nodes.append(obj_node)

                # Create Goal Nodes
                for g_data in obj_data.get("goals", []):
                    goal_node = ObjectiveNode(
                        id=f"goal_{datetime.now().strftime('%Y%m%d%H%M%S')}_{len(nodes)}",
                        title=g_data.get("title", "Unnamed Goal"),
                        description=g_data.get("description", ""),
                        layer=GoalLayer.GOAL,
                        source=GoalSource.TOP_DOWN,
                        deadline=g_data.get("deadline"),
                        parent_id=obj_id
                    )
                    nodes.append(goal_node)
                    obj_node.children_ids.append(goal_node.id)

    return nodes
