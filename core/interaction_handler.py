import json
from typing import Dict, Any, List
from pydantic import BaseModel

from core.goal_service import GoalService
from core.llm_adapter import get_llm
from core.objective_engine.models import GoalState
from core.objective_engine.registry import GoalRegistry

class InteractionResponse(BaseModel):
    response_text: str
    action_type: str  # "UPDATE_IDENTITY", "GOAL_FEEDBACK", "CHAT", "NONE"
    updated_fields: List[str] = []
    updates: Dict[str, Any] = {}

PROMPT_TEMPLATE = """
You are the Steward of an AI Life OS. You are interacting with the User directly.
Your goal is to parse their message and decide what action to take.

Current System State:
{state_summary}

Current Active Goals:
{active_goals}

User Message: "{user_message}"

Determine the user's intent:
1. UPDATE_IDENTITY: User is providing personal info (name, job, city, habit, etc.).
   - Extract the fields to update in "identity" or "constraints".
   - valid fields: identity.name, identity.city, identity.occupation,
     identity.bio, constraints.work_hours, constraints.sleep_hours.
2. GOAL_FEEDBACK: User is providing feedback on a SPECIFIC active goal or general progress.
   - If they allow it, infer which goal they mean.
   - extract feedback intent: COMPLETE, SKIP, DEFER, BLOCKED.
3. CHAT: General question or chat.

Return JSON format:
{{
    "intent": "UPDATE_IDENTITY" | "GOAL_FEEDBACK" | "CHAT",
    "reply": "Natural language reply to the user (keep it concise, friendly, 'Steward' persona)",
    "updates": {{
        "identity.city": "New York",
        "goal_id_123": "COMPLETE"
    }}
}}
"""

class InteractionHandler:
    def __init__(self, registry: GoalRegistry, state: Dict[str, Any]):
        self.registry = registry
        self.state = state
        # Use Strategic Brain for better conversation context
        self.llm = get_llm("strategic_brain")

    def process(self, message: str) -> InteractionResponse:
        # Prepare context
        active_goals = [
            f"[{g.id}] {g.title}"
            for g in self.registry.goals
            if g.state == GoalState.ACTIVE
        ]
        state_summary = json.dumps(self.state.get("identity", {}), ensure_ascii=False)

        prompt = PROMPT_TEMPLATE.format(
            state_summary=state_summary,
            active_goals="\n".join(active_goals) if active_goals else "None",
            user_message=message
        )

        try:
            print("[Interaction] Sending prompt to LLM...")
            # Use generate() from LLMAdapter interface
            llm_resp = self.llm.generate(prompt)
            if not llm_resp.success:
                raise Exception(f"LLM Generation Failed: {llm_resp.error}")

            raw_resp = llm_resp.content
            print(f"[Interaction] Raw Resp: {raw_resp}")

            # Robust JSON extraction
            import re
            json_match = re.search(r'\{.*\}', raw_resp, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)
            else:
                cleaned = raw_resp

            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                # Fallback: try to fix common JSON errors or just fail gracefully
                print("[Interaction] JSON Decode Error. Fallback to CHAT.")
                data = {
                    "intent": "CHAT",
                    "reply": raw_resp or "I didn't quite catch that (JSON Error).",
                }

            intent = data.get("intent", "CHAT")
            reply = data.get("reply", "System processed your request.")
            updates = data.get("updates", {})

            updated_fields = []

            # Execute Updates
            if intent == "UPDATE_IDENTITY":
                self._update_identity(updates)
                updated_fields = list(updates.keys())

            elif intent == "GOAL_FEEDBACK":
                self._handle_goal_feedback(updates)
                updated_fields = list(updates.keys())

            return InteractionResponse(
                response_text=reply,
                action_type=intent,
                updated_fields=updated_fields,
                updates=updates
            )

        except Exception as e:
            print(f"Interaction Error: {e}")
            return InteractionResponse(
                response_text=f"System Error: {str(e)}",
                action_type="ERROR"
            )

    def _update_identity(self, updates: Dict[str, Any]):
        # This requires State to be mutable and persisted.
        # For now, we update the dict, calling code must save it.
        identity = self.state.setdefault("identity", {})
        constraints = self.state.setdefault("constraints", {})

        for k, v in updates.items():
            if k.startswith("identity."):
                field = k.split(".")[1]
                identity[field] = v
            elif k.startswith("constraints."):
                field = k.split(".")[1]
                constraints[field] = v

    def _handle_goal_feedback(self, updates: Dict[str, Any]):
        service = GoalService(registry=self.registry)

        for k, v in updates.items():
            goal = self.registry.get_node(k)
            if not goal:
                continue

            status = str(v).strip().lower()
            if status in {"complete", "skip", "blocked", "defer", "partial"}:
                service.apply_feedback(k, status)
