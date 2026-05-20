"""
Voice telephony endpoints using Twilio.
Twilio calls this webhook, we respond with TwiML XML.
"""
import asyncio
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.dependencies import get_db_session
from app.models.schemas import TenantConfig
from app.services.session_service import SessionService
from app.services.tenant_service import TenantService
from app.agents.support_agent import get_agent_for_channel

try:
    from twilio.twiml.voice_response import VoiceResponse, Gather
    TWILIO_INSTALLED = True
except ImportError:
    TWILIO_INSTALLED = False
    class VoiceResponse:
        def __init__(self):
            self._parts = []
        def say(self, text, **kw):
            voice = kw.get("voice", "Polly.Matthew-Neural")
            self._parts.append(f'<Say voice="{voice}">{text}</Say>')
        def pause(self, length=1):
            self._parts.append(f'<Pause length="{length}"/>')
        def gather(self, **kw):
            g = Gather(**kw)
            self._parts.append(g)
            return g
        def append(self, g):
            self._parts.append(g)
        def __str__(self):
            inner = "".join(str(p) for p in self._parts)
            return f'<?xml version="1.0" encoding="UTF-8"?><Response>{inner}</Response>'

    class Gather:
        def __init__(self, **kw):
            self._attrs = " ".join(f'{k}="{v}"' for k, v in kw.items())
            self._inner = []
        def say(self, text, **kw):
            voice = kw.get("voice", "Polly.Matthew-Neural")
            self._inner.append(f'<Say voice="{voice}">{text}</Say>')
        def __str__(self):
            inner = "".join(self._inner)
            return f'<Gather {self._attrs}>{inner}</Gather>'

logger = get_logger(__name__)
router = APIRouter()

# Voice LLM timeout — generous because TTS adds latency
VOICE_LLM_TIMEOUT = 120


@router.post("/webhook/{tenant_id}")
async def twilio_voice_webhook(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Twilio webhook endpoint. Twilio calls this on every turn of the phone call.
    Returns TwiML XML that tells Twilio what to say and what to listen for next.

    Configure in Twilio Console:
      Voice → Phone Numbers → Your Number → A Call Comes In → Webhook
      URL: https://<your-ngrok-url>/api/twilio/webhook/<tenant_id>
      Method: HTTP POST
    """
    form_data = await request.form()

    user_speech  = form_data.get("SpeechResult", "").strip()
    caller_phone = form_data.get("From", "anonymous")
    call_sid     = form_data.get("CallSid", "unknown-call")

    logger.info(
        "Twilio webhook received",
        tenant_id=tenant_id,
        call_sid=call_sid,
        has_speech=bool(user_speech),
    )

    session_service = SessionService(db)
    tenant_service  = TenantService(db)

    session = await session_service.get_or_create_session(
        tenant_id=tenant_id,
        customer_id=caller_phone,
        channel="voice",
        session_id=call_sid,
    )

    response = VoiceResponse()

    if not user_speech:
        # First turn — greet the caller
        _tenant_obj = await tenant_service.get_tenant_by_id_or_slug(tenant_id)
        persona = _tenant_obj.config.get("persona_name", "Aria") if _tenant_obj else "Aria"
        greeting = (
            f"Hello, you've reached {persona}, your AI support assistant. "
            "Please describe your issue or ask me anything."
        )
        g = Gather(
            input="speech",
            action=f"/api/twilio/webhook/{tenant_id}",
            timeout="5",
            speechTimeout="auto",
            language="en-US",
        )
        g.say(greeting, voice="Polly.Matthew-Neural")
        response.append(g)
        response.say(
            "I didn't catch that. Please call again and describe your issue.",
            voice="Polly.Matthew-Neural",
        )
    else:
        # Subsequent turns — send speech to the agent
        logger.info("Voice speech received", text_preview=user_speech[:80])
        await session_service.add_message(session.id, "user", user_speech)
        history = await session_service.get_history(session.id)

        _tenant_obj = await tenant_service.get_tenant_by_id_or_slug(tenant_id)
        tenant_config = TenantConfig(**_tenant_obj.config) if _tenant_obj else TenantConfig()
        # KB is indexed by slug, not UUID
        kb_tenant_id = _tenant_obj.slug if _tenant_obj else tenant_id

        agent = get_agent_for_channel(
            channel="voice",
            tenant_config=tenant_config,
            tenant_id=kb_tenant_id,
        )

        try:
            result = await asyncio.wait_for(
                agent.invoke(user_input=user_speech, history=history),
                timeout=VOICE_LLM_TIMEOUT,
            )
            ai_reply = result.get("output", "")
            if not ai_reply:
                ai_reply = "I'm sorry, I had trouble generating a response. Please try again."

            await session_service.add_message(session.id, "assistant", ai_reply)
            logger.info("Voice reply generated", reply_preview=ai_reply[:80])

        except asyncio.TimeoutError:
            logger.error("Voice LLM timeout", call_sid=call_sid)
            ai_reply = (
                "I'm sorry, that took too long. "
                "Please rephrase your question and I'll try again."
            )
        except Exception as e:
            logger.error("Voice agent error", error=str(e)[:200])
            ai_reply = "I'm experiencing a technical issue. Please hold while I reconnect."

        # Speak the reply, then listen for the next turn
        g = Gather(
            input="speech",
            action=f"/api/twilio/webhook/{tenant_id}",
            timeout="5",
            speechTimeout="auto",
            language="en-US",
        )
        g.say(ai_reply, voice="Polly.Matthew-Neural")
        response.append(g)
        response.say(
            "Are you still there? Please go ahead with your question.",
            voice="Polly.Matthew-Neural",
        )

    return HTMLResponse(content=str(response), media_type="application/xml")
