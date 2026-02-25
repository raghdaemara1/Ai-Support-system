"""
Voice telelphony endpoints using Twilio and Deepgram.
This satisfies the 'Voice' channel requirement for enterprise deployments.
"""
import os
import json
from fastapi import APIRouter, Request, BackgroundTasks, Depends
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.dependencies import get_db_session
from app.services.session_service import SessionService
from app.services.tenant_service import TenantService
from app.agents.support_agent import get_agent_for_channel

# In a real enterprise setup, we install the twilio package
try:
    from twilio.twiml.voice_response import VoiceResponse, Gather
except ImportError:
    # Fallback dummies for local development without twilio installed
    class VoiceResponse:
        def __init__(self): self.xml = ""
        def say(self, text, **kw): self.xml += f"<Say>{text}</Say>"
        def pause(self, length): self.xml += f"<Pause length='{length}'/>"
        def gather(self, **kw): return Gather()
        def append(self, g): self.xml += "<Gather/>"
        def __str__(self): return f"<Response>{self.xml}</Response>"
    class Gather:
        def say(self, text, **kw): pass

logger = get_logger(__name__)
router = APIRouter()


@router.post("/twilio/webhook/{tenant_id}")
async def twilio_voice_webhook(
    tenant_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session),
):
    """
    Twilio handles the inbound phone call and hits this webhook.
    We return TwiML XML instructing Twilio to read text aloud and transcribe user speech.
    """
    form_data = await request.form()
    
    # Twilio sends the transcribed text in the 'SpeechResult' field
    user_speech = form_data.get("SpeechResult", "").strip()
    caller_phone = form_data.get("From", "Unknown")
    call_sid = form_data.get("CallSid", "UnknownSession")
    
    session_service = SessionService(db)
    tenant_service = TenantService(db)
    
    # Get or create session based on caller's phone number
    session = await session_service.get_or_create_session(
        tenant_id=tenant_id,
        customer_id=caller_phone,
        channel="voice",
        session_id=call_sid
    )
    
    response = VoiceResponse()
    
    if not user_speech:
        # First time the user calls
        ai_reply = "Welcome to Enterprise Support. Please describe your issue or read me the fault code."
    else:
        logger.info("Voice Input Received", phone=caller_phone, text=user_speech)
        await session_service.add_message(session.id, "user", user_speech)
        history = await session_service.get_history(session.id)
        
        tenant_config = await tenant_service.get_config(tenant_id)
        
        # We explicitly request the 'voice' agent, which has a shorter, punchier system prompt
        agent = get_agent_for_channel(
            channel="voice",
            tenant_config=tenant_config,
            tenant_id=tenant_id,
        )
        
        try:
            # We invoke LangGraph just like we do in chat and email!
            result = await agent.invoke(user_input=user_speech, history=history)
            ai_reply = result.get("output", "I'm sorry, I encountered an error answering that.")
            await session_service.add_message(session.id, "assistant", ai_reply)
        except Exception as e:
            logger.error("Voice Agent Error", error=str(e))
            ai_reply = "I apologize, my systems are currently experiencing a delay. Please try again."

    # Return the AI's response to Twilio as spoken audio, and open the mic for the next turn
    response.say(ai_reply, voice="Polly.Matthew-Neural")
    g = Gather(input="speech", action=f"/api/twilio/twilio/webhook/{tenant_id}", timeout=5)
    response.append(g)
    
    # If they don't say anything after 5 seconds, politely ask again
    response.say("Are you still there? Please describe your issue.")
    response.pause(length=2)
    
    return HTMLResponse(content=str(response), media_type="application/xml")
