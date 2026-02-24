from fastapi import APIRouter, Request
from fastapi.responses import Response

from app.agent.support_agent import SupportAgent
from app.storage.session import SessionManager

router = APIRouter()
_session_manager = SessionManager()
_agent: SupportAgent | None = None


def _get_agent() -> SupportAgent:
    global _agent
    if _agent is None:
        _agent = SupportAgent()
    return _agent


@router.post("/voice/incoming")
async def handle_incoming_call(request: Request):
    _ = request
    twiml = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
    <Say voice=\"Polly.Joanna\">Hello, you reached the industrial support agent. Please describe your issue or alarm code.</Say>
    <Gather input=\"speech\" action=\"/api/voice/transcribed\" speechTimeout=\"auto\" language=\"en-US\"></Gather>
    <Say voice=\"Polly.Joanna\">I did not hear anything. Please call back.</Say>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/transcribed")
async def handle_transcription(request: Request):
    form = await request.form()
    user_text = str(form.get("SpeechResult", ""))
    call_sid = str(form.get("CallSid", "unknown"))

    session = _session_manager.get_or_create(call_sid, channel="voice")
    response = await _get_agent().respond(message=user_text, session=session)

    safe_text = response.content.replace("&", "and").replace("<", "").replace(">", "")

    if response.escalate:
        twiml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
    <Say voice=\"Polly.Joanna\">{safe_text}</Say>
    <Say voice=\"Polly.Joanna\">I am now connecting you to a human engineer. Please hold.</Say>
</Response>"""
    else:
        twiml = f"""<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Response>
    <Say voice=\"Polly.Joanna\">{safe_text}</Say>
    <Gather input=\"speech\" action=\"/api/voice/transcribed\" speechTimeout=\"auto\">
        <Say voice=\"Polly.Joanna\">Is there anything else I can help you with?</Say>
    </Gather>
</Response>"""

    return Response(content=twiml, media_type="application/xml")
