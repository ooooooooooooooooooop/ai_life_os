import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel

from core.goal_service import GoalService
from core.llm_adapter import get_llm
from core.objective_engine.models import GoalState
from core.objective_engine.registry import GoalRegistry
from core.intent_recognition import EnhancedIntentRecognizer, IntentResult

class InteractionResponse(BaseModel):
    response_text: str
    action_type: str  # "UPDATE_IDENTITY", "GOAL_FEEDBACK", "ASK", "CONFIRM", "CANCEL", "CHAT", "NONE"
    updated_fields: List[str] = []
    updates: Dict[str, Any] = {}
    confidence: float = 1.0
    needs_clarification: bool = False
    clarification_options: List[str] = []

PROMPT_TEMPLATE = """
You are the Steward of an AI Life OS. You are interacting with the User directly.
Your goal is to parse their message and decide what action to take.

Current System State:
{state_summary}

Current Active Goals:
{active_goals}

{mood_hint}

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
    def __init__(self, registry: GoalRegistry, state: Dict[str, Any], use_enhanced: bool = True):
        self.registry = registry
        self.state = state
        # Use Strategic Brain for better conversation context
        self.llm = get_llm("strategic_brain")

        # Initialize enhanced intent recognizer
        self.use_enhanced = use_enhanced
        if use_enhanced:
            self.intent_recognizer = EnhancedIntentRecognizer(self.llm)

    def process(self, message: str) -> InteractionResponse:
        # Prepare context
        active_goals = [
            f"[{g.id}] {g.title}"
            for g in self.registry.goals
            if g.state == GoalState.ACTIVE
        ]
        state_summary = json.dumps(self.state.get("identity", {}), ensure_ascii=False)

        # Use enhanced intent recognizer if enabled
        if self.use_enhanced:
            return self._process_enhanced(message, state_summary, active_goals)
        else:
            return self._process_legacy(message, state_summary, active_goals)

    def _process_enhanced(
        self, message: str, state_summary: str, active_goals: List[str]
    ) -> InteractionResponse:
        """Process message using enhanced intent recognizer."""
        try:
            # Recognize intent
            result = self.intent_recognizer.recognize_intent(
                message, state_summary, active_goals
            )

            updated_fields = []

            # Handle different intents
            if result.intent == "UPDATE_IDENTITY":
                self._update_identity(result.updates)
                updated_fields = list(result.updates.keys())

            elif result.intent == "GOAL_FEEDBACK":
                self._handle_goal_feedback(result.updates)
                updated_fields = list(result.updates.keys())

            elif result.intent == "ASK":
                # Handle ASK intent
                ask_type = result.updates.get("ask_type", "ASK_STATUS")
                reply = self.intent_recognizer.handle_ask_intent(
                    ask_type, self.state, self.registry.goals
                )
                result.reply = reply

            elif result.intent == "CONFIRM":
                # Handle confirmation
                result.reply = "Action confirmed. Proceeding..."

            elif result.intent == "CANCEL":
                # Handle cancellation
                result.reply = "Action cancelled."

            # 对话记忆摘要
            from core.conversation_summarizer import summarize_and_save
            summarize_and_save(message, result.reply, result.intent)

            return InteractionResponse(
                response_text=result.reply,
                action_type=result.intent,
                updated_fields=updated_fields,
                updates=result.updates,
                confidence=result.confidence,
                needs_clarification=result.needs_clarification,
                clarification_options=result.clarification_options,
            )

        except Exception as e:
            print(f"Enhanced Interaction Error: {e}")
            return InteractionResponse(
                response_text=f"System Error: {str(e)}",
                action_type="ERROR",
                confidence=0.0,
            )

    def _process_legacy(
        self, message: str, state_summary: str, active_goals: List[str]
    ) -> InteractionResponse:
        """Process message using legacy method (backward compatibility)."""
        from core.mood_detector import detect_mood
        mood = detect_mood(message)
        mood_hint = f"用户当前情绪状态检测：{mood}，请相应调整回复语气。"

        prompt = PROMPT_TEMPLATE.format(
            state_summary=state_summary,
            active_goals="\n".join(active_goals) if active_goals else "None",
            mood_hint=mood_hint,
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

            # 对话记忆摘要
            from core.conversation_summarizer import summarize_and_save
            summarize_and_save(message, reply, intent)

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
