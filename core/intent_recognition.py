"""
Enhanced Intent Recognition Module for AI Life OS.

This module provides advanced intent recognition with:
- Extended intent types (ASK, CONFIRM, CANCEL)
- Confidence scoring
- Multi-turn conversation support
- Clarification mechanism

Part of uncertainty handling optimization.
"""

import json
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class IntentResult(BaseModel):
    """Result of intent recognition."""
    intent: str
    confidence: float = Field(ge=0.0, le=1.0)
    reply: str
    updates: Dict[str, Any] = {}
    needs_clarification: bool = False
    clarification_options: List[str] = []


class ConversationContext(BaseModel):
    """Context for multi-turn conversation."""
    history: List[Dict[str, Any]] = []
    current_topic: Optional[str] = None
    last_intent: Optional[str] = None
    pending_action: Optional[str] = None


# Extended intent types
INTENT_TYPES = {
    "UPDATE_IDENTITY": "User is providing personal information",
    "GOAL_FEEDBACK": "User is providing feedback on goals",
    "ASK": "User is asking questions about system state or suggestions",
    "CONFIRM": "User is confirming an action",
    "CANCEL": "User is canceling an action",
    "CHAT": "General conversation",
}


# Enhanced prompt template with few-shot examples
ENHANCED_PROMPT_TEMPLATE = """
You are the Steward of an AI Life OS. You are interacting with the User directly.
Your goal is to parse their message and decide what action to take.

Current System State:
{state_summary}

Current Active Goals:
{active_goals}

Conversation History (last 3 turns):
{conversation_history}

User Message: "{user_message}"

Determine the user's intent and confidence level:

1. UPDATE_IDENTITY: User is providing personal info (name, job, city, habit, etc.).
   - Extract the fields to update in "identity" or "constraints".
   - Valid fields: identity.name, identity.city, identity.occupation, identity.bio,
     constraints.work_hours, constraints.sleep_hours.
   - Example: "I live in New York" -> UPDATE_IDENTITY with identity.city="New York"

2. GOAL_FEEDBACK: User is providing feedback on a SPECIFIC active goal or general progress.
   - Infer which goal they mean if possible.
   - Extract feedback intent: COMPLETE, SKIP, DEFER, BLOCKED.
   - Example: "I finished the first task" -> GOAL_FEEDBACK with goal_id="COMPLETE"

3. ASK: User is asking questions about system state, suggestions, or progress.
   - Types: ASK_STATUS (how am I doing?), ASK_SUGGESTION (what should I do?),
     ASK_PROGRESS (what's my progress?), ASK_HELP (how does this work?).
   - Example: "How am I doing today?" -> ASK with type="ASK_STATUS"

4. CONFIRM: User is confirming an action.
   - Example: "Yes, do it" -> CONFIRM

5. CANCEL: User is canceling an action.
   - Example: "No, never mind" -> CANCEL

6. CHAT: General question or chat that doesn't fit other categories.

Return JSON format:
{{
    "intent": "UPDATE_IDENTITY" | "GOAL_FEEDBACK" | "ASK" | "CONFIRM" | "CANCEL" | "CHAT",
    "confidence": 0.0-1.0,
    "reply": "Natural language reply to the user (keep it concise, friendly, 'Steward' persona)",
    "updates": {{
        "identity.city": "New York",
        "goal_id_123": "COMPLETE"
    }},
    "ask_type": "ASK_STATUS" | "ASK_SUGGESTION" | "ASK_PROGRESS" | "ASK_HELP" (only for ASK intent),
    "needs_clarification": true/false,
    "clarification_options": ["option1", "option2"] (if needs_clarification is true)
}}

Few-shot examples:

User: "I moved to San Francisco"
Response: {{"intent": "UPDATE_IDENTITY", "confidence": 0.95, "reply": "Got it! I've updated your location to San Francisco.", "updates": {{"identity.city": "San Francisco"}}}}

User: "What should I work on next?"
Response: {{"intent": "ASK", "confidence": 0.9, "reply": "Based on your goals, I suggest working on...", "ask_type": "ASK_SUGGESTION"}}

User: "I'm not sure what you mean"
Response: {{"intent": "CHAT", "confidence": 0.7, "reply": "Let me clarify...", "needs_clarification": true, "clarification_options": ["Option 1", "Option 2"]}}
"""


class EnhancedIntentRecognizer:
    """Enhanced intent recognizer with confidence scoring and ASK mode."""

    def __init__(self, llm_adapter):
        """Initialize with LLM adapter."""
        self.llm = llm_adapter
        self.context = ConversationContext()

    def recognize_intent(
        self,
        message: str,
        state_summary: str,
        active_goals: List[str],
    ) -> IntentResult:
        """
        Recognize user intent from message.

        Args:
            message: User's message
            state_summary: Current system state summary
            active_goals: List of active goals

        Returns:
            IntentResult with intent, confidence, and reply
        """
        # Prepare conversation history
        history_str = self._format_history()

        # Create prompt
        prompt = ENHANCED_PROMPT_TEMPLATE.format(
            state_summary=state_summary,
            active_goals="\n".join(active_goals) if active_goals else "None",
            conversation_history=history_str,
            user_message=message,
        )

        try:
            # Get LLM response
            llm_resp = self.llm.generate(prompt)
            if not llm_resp.success:
                raise Exception(f"LLM Generation Failed: {llm_resp.error}")

            raw_resp = llm_resp.content

            # Extract JSON
            json_match = re.search(r'\{.*\}', raw_resp, re.DOTALL)
            if json_match:
                cleaned = json_match.group(0)
            else:
                cleaned = raw_resp

            # Parse JSON
            try:
                data = json.loads(cleaned)
            except json.JSONDecodeError:
                # Fallback to CHAT
                data = {
                    "intent": "CHAT",
                    "confidence": 0.5,
                    "reply": raw_resp or "I didn't quite catch that.",
                }

            # Extract fields
            intent = data.get("intent", "CHAT")
            confidence = float(data.get("confidence", 0.5))
            reply = data.get("reply", "System processed your request.")
            updates = data.get("updates", {})
            needs_clarification = data.get("needs_clarification", False)
            clarification_options = data.get("clarification_options", [])

            # Update conversation context
            self._update_context(message, intent, confidence)

            return IntentResult(
                intent=intent,
                confidence=confidence,
                reply=reply,
                updates=updates,
                needs_clarification=needs_clarification,
                clarification_options=clarification_options,
            )

        except Exception as e:
            print(f"Intent Recognition Error: {e}")
            return IntentResult(
                intent="ERROR",
                confidence=0.0,
                reply=f"System Error: {str(e)}",
            )

    def _format_history(self, max_turns: int = 3) -> str:
        """Format conversation history for prompt."""
        if not self.context.history:
            return "No previous conversation."

        recent = self.context.history[-max_turns:]
        lines = []
        for turn in recent:
            user_msg = turn.get("user", "")
            intent = turn.get("intent", "")
            lines.append(f"User: {user_msg} -> Intent: {intent}")

        return "\n".join(lines)

    def _update_context(self, message: str, intent: str, confidence: float):
        """Update conversation context."""
        self.context.history.append({
            "user": message,
            "intent": intent,
            "confidence": confidence,
            "timestamp": datetime.now().isoformat(),
        })
        self.context.last_intent = intent

        # Keep only last 10 turns
        if len(self.context.history) > 10:
            self.context.history = self.context.history[-10:]

    def handle_ask_intent(
        self,
        ask_type: str,
        state: Dict[str, Any],
        goals: List[Any],
    ) -> str:
        """
        Handle ASK intent based on type.

        Args:
            ask_type: Type of ASK (ASK_STATUS, ASK_SUGGESTION, etc.)
            state: Current system state
            goals: List of goals

        Returns:
            Response string
        """
        if ask_type == "ASK_STATUS":
            return self._handle_status_query(state, goals)
        elif ask_type == "ASK_SUGGESTION":
            return self._handle_suggestion_query(state, goals)
        elif ask_type == "ASK_PROGRESS":
            return self._handle_progress_query(state, goals)
        elif ask_type == "ASK_HELP":
            return self._handle_help_query()
        else:
            return "I'm not sure what you're asking. Could you be more specific?"

    def _handle_status_query(self, state: Dict[str, Any], goals: List[Any]) -> str:
        """Handle status query."""
        active_goals = [g for g in goals if g.state == "ACTIVE"]
        completed_today = len([g for g in goals if g.state == "COMPLETED"])

        return (
            f"You have {len(active_goals)} active goals. "
            f"You've completed {completed_today} goals today. "
            f"Keep up the good work!"
        )

    def _handle_suggestion_query(self, state: Dict[str, Any], goals: List[Any]) -> str:
        """Handle suggestion query."""
        active_goals = [g for g in goals if g.state == "ACTIVE"]
        if not active_goals:
            return "You don't have any active goals. Would you like to create one?"

        # Simple suggestion: pick highest priority goal
        high_priority = sorted(active_goals, key=lambda g: g.priority, reverse=True)[0]
        return f"I suggest working on '{high_priority.title}' as it's your highest priority goal."

    def _handle_progress_query(self, state: Dict[str, Any], goals: List[Any]) -> str:
        """Handle progress query."""
        total = len(goals)
        completed = len([g for g in goals if g.state == "COMPLETED"])
        progress = (completed / total * 100) if total > 0 else 0

        return f"You've completed {completed} out of {total} goals ({progress:.1f}% progress)."

    def _handle_help_query(self) -> str:
        """Handle help query."""
        return (
            "I can help you with:\n"
            "- Managing your goals\n"
            "- Tracking your progress\n"
            "- Providing suggestions\n"
            "- Answering questions about your system\n"
            "Just ask me anything!"
        )

    def reset_context(self):
        """Reset conversation context."""
        self.context = ConversationContext()
