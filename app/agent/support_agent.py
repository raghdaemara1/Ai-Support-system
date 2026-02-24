import os
import re

from app.agent.escalation import EscalationEngine
from app.agent.rag_pipeline import RAGPipeline
from app.agent.tools import ToolExecutor
from app.models.agent_models import AgentResponse, KBSearchResult, MessageRole, Session

SYSTEM_PROMPT = """You are an expert industrial support agent for O3Sigma-managed manufacturing equipment.
Use provided KB facts and avoid guessing. Keep responses concise and action-focused."""


class SupportAgent:
    def __init__(self):
        self.rag = RAGPipeline()
        self.tools = ToolExecutor()
        self.escalate = EscalationEngine()
        self.model = os.environ.get("GROQ_MODEL", "llama3-8b-8192")
        self.client = self._build_groq_client()

    def _build_groq_client(self):
        api_key = os.environ.get("GROQ_API_KEY", "").strip()
        if not api_key:
            return None

        try:
            from groq import Groq

            return Groq(api_key=api_key)
        except Exception:
            return None

    async def respond(self, message: str, session: Session) -> AgentResponse:
        kb_results = self.rag.search(message, machine=session.machine, top_k=3)
        kb_context = self._format_kb_context(kb_results)

        content = self._generate_response(message=message, session=session, kb_context=kb_context)

        confidence = self._estimate_confidence(kb_results)
        should_escalate = self.escalate.should_escalate(
            message=message,
            response=content,
            session=session,
            confidence=confidence,
        )

        ticket = None
        if should_escalate or self._agent_is_unsure(content):
            ticket = self.tools.create_ticket(
                session_id=session.session_id,
                channel=session.channel.value,
                summary=message[:200],
                machine=session.machine,
                alarm_code=self._extract_alarm_code(message),
            )

        return AgentResponse(
            session_id=session.session_id,
            content=content,
            confidence=confidence,
            intent=self._classify_intent(message),
            tool_used="kb_lookup" if kb_results else None,
            escalate=should_escalate,
            ticket_created=ticket,
            sources=[r.description[:80] for r in kb_results],
        )

    def _generate_response(self, message: str, session: Session, kb_context: str) -> str:
        if self.client:
            history = self._build_history(session=session, user_message=message, kb_context=kb_context)
            try:
                completion = self.client.chat.completions.create(
                    model=self.model,
                    messages=history,
                    temperature=0.2,
                    max_tokens=400,
                )
                return completion.choices[0].message.content
            except Exception:
                pass

        # Deterministic fallback for local demos when LLM is not configured.
        return self._fallback_response(message=message, kb_context=kb_context)

    def _fallback_response(self, message: str, kb_context: str) -> str:
        if "No matching records found" in kb_context:
            return (
                "What this alarm means: I could not find a matching record in the knowledge base.\n"
                "Likely cause: Unknown from current indexed manuals.\n"
                "What to do: 1) Share machine name and alarm code. 2) I can create a ticket for an engineer."
            )

        first_line = kb_context.splitlines()[0]
        return (
            f"What this alarm means: {first_line}.\n"
            "Likely cause: Based on KB records linked to this alarm.\n"
            "What to do: 1) Follow the corrective action from KB. 2) Confirm machine state. 3) Escalate if unresolved."
        )

    def _format_kb_context(self, results: list[KBSearchResult]) -> str:
        if not results:
            return "No matching records found in knowledge base."

        parts = []
        for result in results:
            parts.append(
                f"Alarm {result.alarm_id}: {result.description}\n"
                f"Cause: {result.cause or 'not specified'}\n"
                f"Action: {result.action or 'not specified'}"
            )
        return "\n\n".join(parts)

    def _build_history(self, session: Session, user_message: str, kb_context: str) -> list[dict[str, str]]:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"KNOWLEDGE BASE:\n{kb_context}"},
        ]
        for msg in session.history[-6:]:
            role = "assistant"
            if msg.role == MessageRole.USER:
                role = "user"
            messages.append({"role": role, "content": msg.content})

        messages.append({"role": "user", "content": user_message})
        return messages

    def _extract_alarm_code(self, text: str) -> str | None:
        match = re.search(r"\b(\d{3,5})\b", text)
        return match.group(1) if match else None

    def _classify_intent(self, message: str) -> str:
        text = message.lower()
        if any(token in text for token in ["alarm", "fault", "error", "code"]):
            return "fault_lookup"
        if any(token in text for token in ["ticket", "report", "log"]):
            return "ticket_create"
        if any(token in text for token in ["escalate", "engineer", "human", "help"]):
            return "escalate"
        return "general"

    def _estimate_confidence(self, kb_results: list[KBSearchResult]) -> float:
        if not kb_results:
            return 0.3
        return min(0.95, 0.5 + kb_results[0].score * 0.5)

    def _agent_is_unsure(self, content: str) -> bool:
        signals = ["don't know", "cannot find", "no record", "not in", "unclear", "no information", "consult"]
        text = content.lower()
        return any(signal in text for signal in signals)
