# CLAUDE.md — Multi-Channel AI Support Agent Platform
## Architecture Reference · Demo Build Guide · FDE Interview Portfolio

> This file is the single source of truth for building this platform.
> Read every section before touching any file. Every decision here is
> intentional and maps directly to what a Forward Deployed Engineer at
> a voice/chat/email AI startup would actually build and deploy.

---

## 1. What This Platform Does

An enterprise customer submits a support request — by voice call, live chat,
or email. The AI agent handles it end-to-end: understands the request, searches
a knowledge base for answers, takes action (escalates, creates tickets, updates
records), and responds in the right channel with the right tone.

```
Channels IN:    Voice call  |  Live chat (WebSocket)  |  Email (IMAP/SMTP)
Agent does:     Understand intent -> Search KB -> Act -> Respond -> Escalate if needed
Channels OUT:   Voice reply  |  Chat message  |  Email reply  |  Ticket created
```

Demo scenario (manufacturing support — connects to your O3Sigma background):
A plant operator calls in or chats about a machine alarm. The agent looks up the
fault in the knowledge base (your existing MongoDB alarm records), gives the
operator the cause and fix, and if unresolved, creates a support ticket and
escalates to a human engineer.

This is real. Every layer described below is a working free-tier implementation.

---

## 2. Full Architecture — All Layers

```
+-----------------------------------------------------------------------+
|                         CHANNEL LAYER                                 |
|  Voice  (Twilio + Deepgram STT + ElevenLabs TTS)                     |
|  Chat   (FastAPI WebSocket -> Streamlit frontend)                     |
|  Email  (IMAP polling -> SMTP reply via Gmail)                        |
+------------------------------+----------------------------------------+
                               | normalized text input
+------------------------------v----------------------------------------+
|                      ORCHESTRATION LAYER                              |
|  AgentRouter    -- decides which agent handles the request            |
|  SessionManager -- tracks conversation state per user + channel       |
|  EscalationEngine -- detects handoff triggers, routes to human       |
+------------------------------+----------------------------------------+
                               | structured intent + context
+------------------------------v----------------------------------------+
|                        AGENT LAYER                                    |
|  SupportAgent  -- main LLM agent (Groq llama3-8b, free tier)        |
|  RAGPipeline   -- knowledge base retrieval (ChromaDB + MiniLM)      |
|  ToolExecutor  -- runs tools: KB lookup, ticket create, DB query    |
+------------------------------+----------------------------------------+
                               | structured response
+------------------------------v----------------------------------------+
|                       STORAGE LAYER                                   |
|  MongoDB   -- conversations, tickets, escalations                    |
|  ChromaDB  -- vector knowledge base (alarm records, FAQs, manuals)  |
+-----------------------------------------------------------------------+
```

---

## 3. Project File Map — Every File to Build

```
support_agent/
|
+-- main.py                        <- FastAPI app: mounts all routers + WebSocket
|
+-- channels/
|   +-- voice.py                   <- Twilio webhook: STT -> agent -> TTS -> respond
|   +-- chat.py                    <- WebSocket handler: real-time chat session
|   +-- email_handler.py           <- IMAP poller + SMTP responder
|
+-- agent/
|   +-- support_agent.py           <- SupportAgent: LLM + tools + RAG pipeline
|   +-- rag_pipeline.py            <- RAGPipeline: embed query -> search ChromaDB
|   +-- tools.py                   <- ToolExecutor: kb_lookup, create_ticket, escalate
|   +-- escalation.py              <- EscalationEngine: rules + confidence check
|
+-- knowledge_base/
|   +-- builder.py                 <- Ingests alarm records from MongoDB -> ChromaDB
|   +-- loader.py                  <- Queries the ChromaDB collection
|
+-- storage/
|   +-- database.py                <- MongoDB: conversations, tickets, sessions
|   +-- session.py                 <- SessionManager: per-user state across turns
|
+-- schemas/
|   +-- models.py                  <- Pydantic: Message, Ticket, Session, AgentResponse
|
+-- ui/
|   +-- chat_demo.py               <- Streamlit chat UI (for live demo only)
|
+-- config.py                      <- All env vars: API keys, model names, thresholds
+-- .env                           <- Local values (never commit)
+-- requirements.txt
+-- CLAUDE.md                      <- This file
```

---

## 4. Tool Stack — Free Tier for Demo

```
Layer               Free Tool                     Why It Works
-----               ---------                     ------------
LLM (agent brain)   Groq API (llama3-8b-8192)    14,400 req/day free, <1s latency
STT (voice input)   Twilio <Gather speech>        Included in Twilio trial ($15)
TTS (voice output)  Twilio <Say> Polly voices     Included in Twilio trial
Voice gateway       Twilio trial ($15 credit)     Real phone number, webhook ready
Chat transport      FastAPI WebSocket             Built-in Python, no cost
Email               Gmail IMAP/SMTP               Free, works with App Password
Vector DB           ChromaDB (local file)         No server, persistent to disk
Embeddings          all-MiniLM-L6-v2 (local)     80MB, CPU, 384-dim, no API cost
Structured DB       MongoDB Community (local)     Same as your existing CODEX stack
```

Upgrade path for real deployment:
- STT:  Deepgram Nova-2 ($200 free credit, significantly better accuracy)
- TTS:  ElevenLabs (10,000 chars/month free, very natural voice)
- LLM:  GPT-4o or Claude via API (when Groq free tier is insufficient)

Sign-up links (all free, no card required except Twilio):
- Groq: console.groq.com
- Twilio: twilio.com/try-twilio ($15 trial, gives real number)
- Deepgram: deepgram.com (free $200 credit)
- ElevenLabs: elevenlabs.io (free tier)

---

## 5. Schemas — Exact Pydantic Models

Define these first in schemas/models.py before writing any other file.
Everything flows through these models.

```python
# schemas/models.py

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class Channel(str, Enum):
    CHAT  = "chat"
    VOICE = "voice"
    EMAIL = "email"


class MessageRole(str, Enum):
    USER   = "user"
    AGENT  = "agent"
    SYSTEM = "system"


class Message(BaseModel):
    id:         str
    session_id: str
    role:       MessageRole
    content:    str
    channel:    Channel
    timestamp:  datetime = Field(default_factory=datetime.utcnow)
    metadata:   dict = {}  # e.g. {"confidence": 0.92, "intent": "fault_lookup"}


class Session(BaseModel):
    session_id:  str
    channel:     Channel
    user_id:     Optional[str] = None
    machine:     Optional[str] = None  # O3Sigma machine context
    history:     List[Message] = []
    escalated:   bool = False
    created_at:  datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)


class Ticket(BaseModel):
    ticket_id:  str
    session_id: str
    channel:    Channel
    summary:    str
    machine:    Optional[str] = None
    alarm_code: Optional[str] = None
    priority:   Literal["low", "medium", "high", "critical"] = "medium"
    status:     Literal["open", "in_progress", "resolved", "escalated"] = "open"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentResponse(BaseModel):
    session_id:     str
    content:        str           # text to send back to user
    confidence:     float = 1.0   # 0.0-1.0, below threshold triggers escalation
    intent:         Optional[str] = None  # "fault_lookup" | "ticket_create" | "escalate" | "general"
    tool_used:      Optional[str] = None  # "kb_lookup" | "create_ticket" | "db_query"
    escalate:       bool = False
    ticket_created: Optional[Ticket] = None
    sources:        List[str] = []  # KB chunks used for this response


class KBSearchResult(BaseModel):
    alarm_id:    Optional[str] = None
    description: str
    cause:       Optional[str] = None
    action:      Optional[str] = None
    machine:     Optional[str] = None
    score:       float  # cosine similarity 0-1
```

---

## 6. Channel Layer — How Each Channel Works

### 6.1 Chat Channel (WebSocket)

The core channel. Voice and email are wrappers around this same agent logic.

```python
# channels/chat.py

from fastapi import WebSocket
from agent.support_agent import SupportAgent
from storage.session import SessionManager

agent = SupportAgent()
session_manager = SessionManager()


async def chat_websocket_handler(websocket: WebSocket, session_id: str):
    """
    One WebSocket connection = one support session.
    Messages flow: browser sends text -> agent processes -> agent replies.
    """
    await websocket.accept()
    session = session_manager.get_or_create(session_id, channel="chat")

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "")

            session_manager.add_message(session_id, role="user", content=user_text)

            response = await agent.respond(message=user_text, session=session)

            session_manager.add_message(session_id, role="agent", content=response.content)

            await websocket.send_json({
                "message":    response.content,
                "intent":     response.intent,
                "confidence": response.confidence,
                "escalated":  response.escalate,
                "sources":    response.sources,
                "ticket":     response.ticket_created.model_dump()
                              if response.ticket_created else None
            })

            if response.escalate:
                await websocket.send_json({
                    "message":   "Connecting you to a human engineer now...",
                    "escalated": True
                })
                break

    except Exception as e:
        await websocket.send_json({"error": str(e)})
    finally:
        await websocket.close()
```

### 6.2 Voice Channel (Twilio)

Twilio calls your webhook when someone dials your demo number.
Flow: caller speaks -> Twilio transcribes with <Gather speech> -> you run
through agent -> respond with TwiML <Say> -> caller hears the answer.

```python
# channels/voice.py

from fastapi import APIRouter, Request
from fastapi.responses import Response
from agent.support_agent import SupportAgent
from storage.session import SessionManager
import asyncio

router = APIRouter()
agent = SupportAgent()
session_manager = SessionManager()


@router.post("/voice/incoming")
async def handle_incoming_call(request: Request):
    """
    Twilio calls this when a call comes in.
    Greet caller and ask them to speak their issue.
    """
    twiml = """<?xml version="1.0" encoding="UTF-8"?>
    <Response>
        <Say voice="Polly.Joanna">
            Hello, you have reached the industrial support agent.
            Please describe your issue or provide the alarm code.
        </Say>
        <Gather input="speech" action="/api/voice/transcribed"
                speechTimeout="auto" language="en-US">
        </Gather>
        <Say voice="Polly.Joanna">I did not hear anything. Please call back.</Say>
    </Response>"""
    return Response(content=twiml, media_type="application/xml")


@router.post("/voice/transcribed")
async def handle_transcription(request: Request):
    """
    Twilio sends the caller's speech as text here.
    Run through agent. Reply with TwiML.
    """
    form     = await request.form()
    user_text = form.get("SpeechResult", "")
    call_sid  = form.get("CallSid", "unknown")

    session  = session_manager.get_or_create(call_sid, channel="voice")
    response = await agent.respond(message=user_text, session=session)

    # Sanitize text for TwiML (no special XML chars)
    safe_text = response.content.replace("&", "and").replace("<", "").replace(">", "")

    if response.escalate:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">{safe_text}</Say>
            <Say voice="Polly.Joanna">
                I am now connecting you to a human engineer. Please hold.
            </Say>
        </Response>"""
    else:
        twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
        <Response>
            <Say voice="Polly.Joanna">{safe_text}</Say>
            <Gather input="speech" action="/api/voice/transcribed" speechTimeout="auto">
                <Say voice="Polly.Joanna">Is there anything else I can help you with?</Say>
            </Gather>
        </Response>"""

    return Response(content=twiml, media_type="application/xml")
```

### 6.3 Email Channel (Gmail IMAP + SMTP)

```python
# channels/email_handler.py

import imaplib
import smtplib
import email as email_lib
from email.mime.text import MIMEText
import os
import asyncio
from agent.support_agent import SupportAgent
from storage.session import SessionManager

agent = SupportAgent()
session_manager = SessionManager()


def poll_inbox():
    """
    Check Gmail for unread support emails. Process each one and reply.
    Called every 60 seconds by the background task in main.py.
    """
    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_APP_PASSWORD"])
    mail.select("inbox")

    _, message_ids = mail.search(None, "UNSEEN")
    if not message_ids[0]:
        mail.logout()
        return

    for msg_id in message_ids[0].split():
        _, msg_data = mail.fetch(msg_id, "(RFC822)")
        raw = msg_data[0][1]
        msg = email_lib.message_from_bytes(raw)

        sender  = msg["From"]
        subject = msg["Subject"] or "Support Request"
        body    = _get_text_body(msg)

        # Session per sender email
        session_id = f"email_{sender.split('<')[-1].strip('>')}"
        session    = session_manager.get_or_create(session_id, channel="email")

        response = asyncio.run(agent.respond(
            message=f"Subject: {subject}\n\n{body}",
            session=session
        ))

        _send_reply(to=sender, subject=f"Re: {subject}", body=response.content)
        mail.store(msg_id, "+FLAGS", "\\Seen")

    mail.logout()


def _get_text_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                return part.get_payload(decode=True).decode("utf-8", errors="ignore")
    return msg.get_payload(decode=True).decode("utf-8", errors="ignore")


def _send_reply(to: str, subject: str, body: str):
    reply = MIMEText(body)
    reply["Subject"] = subject
    reply["From"]    = os.environ["EMAIL_ADDRESS"]
    reply["To"]      = to
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(os.environ["EMAIL_ADDRESS"], os.environ["EMAIL_APP_PASSWORD"])
        server.sendmail(os.environ["EMAIL_ADDRESS"], to, reply.as_string())
```

---

## 7. Agent Layer — The Core Intelligence

### 7.1 SupportAgent (LLM + Tools + RAG)

```python
# agent/support_agent.py

import os
import re
from groq import Groq
from agent.rag_pipeline import RAGPipeline
from agent.tools import ToolExecutor
from agent.escalation import EscalationEngine
from schemas.models import AgentResponse, Session

SYSTEM_PROMPT = """You are an expert industrial support agent for O3Sigma-managed
manufacturing equipment. You help operators diagnose machine alarms, understand
fault causes, and take corrective action.

Rules:
1. Always use the knowledge base results provided. Never guess fault causes.
2. Give the operator the cause and specific corrective action from the KB.
3. Be concise. Operators are on the factory floor.
4. If the KB has no matching record, say so clearly and offer to create a ticket.
5. If safety is at risk or the issue is unresolved, recommend escalation.

Response format (plain text, no markdown):
What this alarm means: [1 sentence]
Likely cause: [1 sentence from KB]
What to do: [1-3 numbered steps from KB]"""


class SupportAgent:
    def __init__(self):
        self.client   = Groq(api_key=os.environ["GROQ_API_KEY"])
        self.rag      = RAGPipeline()
        self.tools    = ToolExecutor()
        self.escalate = EscalationEngine()
        self.model    = os.environ.get("GROQ_MODEL", "llama3-8b-8192")

    async def respond(self, message: str, session: Session) -> AgentResponse:
        # Step 1: Search knowledge base
        kb_results = self.rag.search(message, machine=session.machine, top_k=3)
        kb_context = self._format_kb_context(kb_results)

        # Step 2: Build LLM messages
        history = self._build_history(session, message, kb_context)

        # Step 3: Call LLM
        completion = self.client.chat.completions.create(
            model=self.model,
            messages=history,
            temperature=0.2,
            max_tokens=400,
        )
        content = completion.choices[0].message.content

        # Step 4: Check escalation
        confidence      = self._estimate_confidence(kb_results)
        should_escalate = self.escalate.should_escalate(
            message=message, response=content,
            session=session, confidence=confidence
        )

        # Step 5: Create ticket if escalating or agent doesn't know
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
            intent=self._classify_intent(message, kb_results),
            tool_used="kb_lookup" if kb_results else None,
            escalate=should_escalate,
            ticket_created=ticket,
            sources=[r.description[:80] for r in kb_results],
        )

    def _format_kb_context(self, results) -> str:
        if not results:
            return "No matching records found in knowledge base."
        parts = []
        for r in results:
            parts.append(
                f"Alarm {r.alarm_id}: {r.description}\n"
                f"  Cause: {r.cause or 'not specified'}\n"
                f"  Action: {r.action or 'not specified'}"
            )
        return "\n\n".join(parts)

    def _build_history(self, session: Session, user_message: str,
                        kb_context: str) -> list:
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "system", "content": f"KNOWLEDGE BASE:\n{kb_context}"}
        ]
        for msg in session.history[-6:]:  # last 6 turns only
            messages.append({
                "role": "user" if msg.role == "user" else "assistant",
                "content": msg.content
            })
        messages.append({"role": "user", "content": user_message})
        return messages

    def _extract_alarm_code(self, text: str):
        match = re.search(r'\b(\d{3,5})\b', text)
        return match.group(1) if match else None

    def _classify_intent(self, message: str, kb_results: list) -> str:
        msg = message.lower()
        if any(w in msg for w in ["alarm", "fault", "error", "code"]):
            return "fault_lookup"
        if any(w in msg for w in ["ticket", "report", "log"]):
            return "ticket_create"
        if any(w in msg for w in ["escalate", "engineer", "human", "help"]):
            return "escalate"
        return "general"

    def _estimate_confidence(self, kb_results: list) -> float:
        if not kb_results:
            return 0.3
        return min(0.95, 0.5 + kb_results[0].score * 0.5)

    def _agent_is_unsure(self, content: str) -> bool:
        signals = ["don't know", "cannot find", "no record", "not in", "unclear",
                   "no information", "consult"]
        return any(s in content.lower() for s in signals)
```

### 7.2 RAG Pipeline (ChromaDB + MiniLM)

```python
# agent/rag_pipeline.py

from sentence_transformers import SentenceTransformer
import chromadb
from schemas.models import KBSearchResult
import os


class RAGPipeline:
    MODEL_NAME = "all-MiniLM-L6-v2"    # 80MB, CPU, free
    COLLECTION = "support_kb"
    CHROMA_DIR = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_db")

    def __init__(self):
        self.model      = SentenceTransformer(self.MODEL_NAME)
        client          = chromadb.PersistentClient(path=self.CHROMA_DIR)
        self.collection = client.get_or_create_collection(
            name=self.COLLECTION,
            metadata={"hnsw:space": "cosine"}
        )

    def search(self, query: str, machine: str = None,
               top_k: int = 3) -> list[KBSearchResult]:
        vector = self.model.encode(query).tolist()
        where  = {"machine": machine} if machine else None
        results = self.collection.query(
            query_embeddings=[vector],
            n_results=top_k,
            where=where,
            include=["metadatas", "distances", "documents"]
        )
        output = []
        for meta, dist, doc in zip(
            results["metadatas"][0],
            results["distances"][0],
            results["documents"][0]
        ):
            output.append(KBSearchResult(
                alarm_id=meta.get("alarm_id"),
                description=meta.get("description", doc[:100]),
                cause=meta.get("cause"),
                action=meta.get("action"),
                machine=meta.get("machine"),
                score=round(1 - dist, 3)
            ))
        return output

    def add_record(self, record_id: str, text: str, metadata: dict):
        vector = self.model.encode(text).tolist()
        self.collection.upsert(
            ids=[record_id],
            embeddings=[vector],
            documents=[text],
            metadatas=[metadata]
        )

    def count(self) -> int:
        return self.collection.count()
```

### 7.3 Escalation Engine

```python
# agent/escalation.py

import re
from schemas.models import Session


class EscalationEngine:
    """Rules-first escalation. Fast and deterministic."""

    HARD_ESCALATE = re.compile(
        r'\b(fire|smoke|injury|emergency|explosion|danger|critical|'
        r'production stop|urgent|unsafe|shutdown)\b', re.IGNORECASE
    )
    AGENT_UNSURE = re.compile(
        r"(don't know|cannot find|not sure|no information|unclear|consult)",
        re.IGNORECASE
    )

    def should_escalate(self, message: str, response: str,
                         session: Session, confidence: float = 1.0) -> bool:
        # 1. Safety emergency — always immediate
        if self.HARD_ESCALATE.search(message):
            return True
        # 2. User wants a human
        if re.search(r'\b(human|engineer|person|speak to|talk to)\b',
                     message, re.IGNORECASE):
            return True
        # 3. Agent admitted it doesn't know
        if self.AGENT_UNSURE.search(response):
            return True
        # 4. Low confidence
        if confidence < float(os.environ.get("ESCALATION_CONFIDENCE_THRESHOLD", 0.4)):
            return True
        # 5. Too many turns without resolution
        if len(session.history) > int(os.environ.get("MAX_TURNS_BEFORE_ESCALATE", 6)) * 2:
            return True
        return False
```

### 7.4 Tools

```python
# agent/tools.py

import uuid
from datetime import datetime
from schemas.models import Ticket, Channel


class ToolExecutor:
    def __init__(self):
        from storage.database import get_database
        self.db = get_database()

    def create_ticket(self, session_id: str, channel: str, summary: str,
                       machine: str = None, alarm_code: str = None,
                       priority: str = "medium") -> Ticket:
        ticket = Ticket(
            ticket_id=f"TKT-{uuid.uuid4().hex[:8].upper()}",
            session_id=session_id,
            channel=Channel(channel),
            summary=summary,
            machine=machine,
            alarm_code=alarm_code,
            priority=priority,
        )
        self.db.save_ticket(ticket)
        return ticket

    def lookup_alarm(self, alarm_code: str, machine: str = None) -> dict | None:
        return self.db.get_alarm(alarm_code=alarm_code, machine=machine)
```

---

## 8. Knowledge Base Builder — Connecting to CODEX Data

This is the bridge between your two systems. Run this after every CODEX
pipeline run to keep the support agent's knowledge base current.

```python
# knowledge_base/builder.py

from agent.rag_pipeline import RAGPipeline
from storage.database import get_database


def build_kb_from_alarms(machine: str = None):
    """
    Load alarm records from MongoDB (extracted by CODEX) and index them
    in ChromaDB so the support agent can search them semantically.
    """
    db  = get_database()
    rag = RAGPipeline()

    if machine:
        alarms = db.get_alarms_for_machine(machine)
    else:
        alarms = list(db.alarms.find({}))

    print(f"Building KB from {len(alarms)} alarm records...")

    for alarm in alarms:
        text = (
            f"Alarm {alarm.get('alarm_id', '')}: "
            f"{alarm.get('description', '')}. "
            f"Cause: {alarm.get('cause', 'unknown')}. "
            f"Action: {alarm.get('action', 'unknown')}."
        )
        metadata = {
            "alarm_id":    str(alarm.get("alarm_id", "")),
            "description": alarm.get("description", "")[:200],
            "cause":       (alarm.get("cause") or "")[:200],
            "action":      (alarm.get("action") or "")[:200],
            "machine":     alarm.get("machine", ""),
            "reason_1":    alarm.get("reason_level_1", ""),
        }
        record_id = f"{alarm.get('machine', 'x')}_{alarm.get('alarm_id', '')}"
        rag.add_record(record_id, text, metadata)

    print(f"Done. Total KB records: {rag.count()}")


if __name__ == "__main__":
    build_kb_from_alarms()
```

---

## 9. FastAPI Main App

```python
# main.py

import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from channels.voice import router as voice_router
from channels.chat import chat_websocket_handler
from channels.email_handler import poll_inbox


@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(email_poll_loop())
    yield

app = FastAPI(title="Multi-Channel AI Support Agent", version="1.0.0",
              lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])
app.include_router(voice_router, prefix="/api")


@app.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await chat_websocket_handler(websocket, session_id)


@app.post("/api/chat")
async def chat_rest(payload: dict):
    """REST endpoint for Streamlit demo (simpler than WebSocket in Streamlit)."""
    from agent.support_agent import SupportAgent
    from storage.session import SessionManager
    agent = SupportAgent()
    sm    = SessionManager()
    session_id = payload.get("session_id", "demo")
    machine    = payload.get("machine")
    session    = sm.get_or_create(session_id, channel="chat")
    if machine:
        session.machine = machine
    response = await agent.respond(message=payload["message"], session=session)
    sm.add_message(session_id, role="user",  content=payload["message"])
    sm.add_message(session_id, role="agent", content=response.content)
    return {
        "message":   response.content,
        "intent":    response.intent,
        "confidence": response.confidence,
        "escalated": response.escalate,
        "sources":   response.sources,
        "ticket":    response.ticket_created.model_dump()
                     if response.ticket_created else None
    }


@app.get("/health")
async def health():
    return {"status": "ok", "channels": ["chat", "voice", "email"]}


async def email_poll_loop():
    while True:
        try:
            poll_inbox()
        except Exception as e:
            print(f"Email poll error: {e}")
        await asyncio.sleep(60)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

---

## 10. Streamlit Demo UI

```python
# ui/chat_demo.py
# Run: streamlit run ui/chat_demo.py

import streamlit as st
import httpx
import uuid

st.set_page_config(page_title="AI Support Agent Demo", page_icon="🤖", layout="wide")
st.title("🤖 Multi-Channel AI Support Agent")
st.caption("Industrial equipment support · Chat · Voice · Email")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Demo Controls")
    machine = st.text_input("Machine Context", value="KHS_Filler")
    st.divider()
    st.subheader("Try these:")
    st.code("Alarm 282 on the KHS Filler line")
    st.code("Error 9093, machine stopped")
    st.code("I need to speak to an engineer")
    st.code("The machine is making a grinding noise")
    st.divider()
    st.caption(f"Session: {st.session_state.session_id[:8]}...")
    st.caption("Voice: dial your Twilio number")
    st.caption("Email: send to your Gmail support address")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("sources"):
            with st.expander(f"KB sources ({len(msg['sources'])})"):
                for s in msg["sources"]:
                    st.caption(f"• {s}")

if prompt := st.chat_input("Describe the issue or enter an alarm code..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.spinner("Agent thinking..."):
        try:
            resp = httpx.post(
                "http://localhost:8000/api/chat",
                json={"message": prompt, "session_id": st.session_state.session_id,
                      "machine": machine},
                timeout=30
            )
            data        = resp.json()
            agent_text  = data.get("message", "Something went wrong.")
            sources     = data.get("sources", [])
            escalated   = data.get("escalated", False)
            ticket      = data.get("ticket")

            st.session_state.messages.append({
                "role": "assistant", "content": agent_text, "sources": sources
            })
            with st.chat_message("assistant"):
                st.write(agent_text)
                if sources:
                    with st.expander(f"Based on {len(sources)} KB records"):
                        for s in sources:
                            st.caption(f"• {s}")
                if escalated:
                    st.warning("Escalated to human engineer")
                if ticket:
                    st.info(f"Ticket created: {ticket['ticket_id']}")
        except Exception as e:
            st.error(f"Agent error: {e}")
            st.info("Make sure the FastAPI backend is running: uvicorn main:app --reload")
```

---

## 11. Environment Variables — Complete .env

```env
# LLM
GROQ_API_KEY=gsk_...
GROQ_MODEL=llama3-8b-8192

# VOICE (Twilio)
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_PHONE_NUMBER=+1XXXXXXXXXX

# EMAIL
EMAIL_ADDRESS=your.support@gmail.com
EMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx

# STORAGE
MONGODB_URI=mongodb://localhost:27017
MONGODB_DATABASE=support_agent_demo
CHROMA_PERSIST_DIR=./chroma_db

# AGENT BEHAVIOR
ESCALATION_CONFIDENCE_THRESHOLD=0.4
MAX_TURNS_BEFORE_ESCALATE=6
DEFAULT_MACHINE=KHS_Filler
```

---

## 12. Installation — Zero to Running

```bash
# 1. Create environment
python -m venv venv && source venv/bin/activate

# 2. Install
pip install -r requirements.txt

# 3. MongoDB
docker run -d --name mongo -p 27017:27017 mongo:7

# 4. Configure
cp .env.example .env
# Fill in: GROQ_API_KEY, TWILIO creds, EMAIL_APP_PASSWORD

# 5. Build knowledge base from your CODEX alarm records
python knowledge_base/builder.py

# 6. Start backend
uvicorn main:app --reload --port 8000

# 7. Start demo UI (separate terminal)
streamlit run ui/chat_demo.py

# 8. Expose for Twilio voice webhook
ngrok http 8000
# Twilio console -> Phone Numbers -> Voice webhook -> https://YOUR-NGROK/api/voice/incoming
```

### requirements.txt

```
fastapi
uvicorn[standard]
websockets
httpx
groq
sentence-transformers
chromadb
pymongo
pydantic>=2.5
python-dotenv
streamlit
twilio
```

---

## 13. Demo Script — What to Show Ryan (10 Minutes)

```
STEP 1 — Chat (3 min)
  Open Streamlit UI
  Type: "Alarm 282 on the KHS Filler line"
  Agent answers with cause and action from KB
  Open "KB Sources" expander — show real alarm records from CODEX pipeline
  Say: "These records come from PDF manuals I processed with the CODEX pipeline.
        Same extraction system — two different deployment surfaces."

STEP 2 — Escalation (1 min)
  Type: "This is an emergency, production has stopped"
  Agent escalates immediately, creates ticket TKT-XXXXXXXX
  Show the ticket ID in the response

STEP 3 — Voice (4 min)
  Call your Twilio number
  Say: "Alarm 9093 on the filling machine"
  Agent responds via voice (Polly.Joanna)
  Full round trip in under 6 seconds
  Show ngrok logs to prove it's real

STEP 4 — Email (2 min)
  Send email to your Gmail support address:
    Subject: "Fault 282 - machine stopped"
    Body: "The KHS Filler is showing alarm 282. What should I do?"
  Wait ~60 seconds
  Show the reply in Gmail — full answer from the agent
```

Key talking point:
"The CODEX pipeline extracts and structures alarm data from PDF manuals.
This support agent consumes that structured data as a knowledge base.
An FDE's job is connecting these two layers for enterprise clients —
which is exactly what this demo shows end to end."

---

## 14. How CODEX and the Support Agent Connect

```
CODEX Pipeline (your Obeikan work)
  |
  PDF Manual -> regex/LLM extraction -> MongoDB alarm records
                                              |
                                              | knowledge_base/builder.py
                                              | reads records, embeds them,
                                              | stores in ChromaDB
                                              |
                                              v
Support Agent (this repo)
  |
  Operator calls / chats / emails with alarm code
  Agent searches ChromaDB -> finds the record
  Agent answers with cause + action from CODEX-extracted data
  If unresolved -> creates ticket -> escalates to engineer
```

One sentence: CODEX is the document intelligence layer.
The support agent is the user-facing deployment layer.
An FDE connects these two layers for each enterprise client.

---

## 15. Immutable Rules

```
RULE 1 — Agent never reads raw PDFs.
  That is CODEX's job. Agent only receives clean records from MongoDB/ChromaDB.

RULE 2 — LLM only generates language, never extracts structured data.
  KB lookup and ticket creation are deterministic tool calls, not LLM work.

RULE 3 — Escalation engine runs rules first, LLM confidence second.
  Safety keywords -> escalate immediately, no LLM check needed.

RULE 4 — Session history capped at 6 turns in the LLM context window.
  Full history is stored in MongoDB. LLM only sees the last 6 messages.

RULE 5 — All three channels produce the same AgentResponse schema.
  Voice, chat, email: agent layer is channel-agnostic.
  Channel layer handles rendering (TwiML / JSON / SMTP).

RULE 6 — Rebuild the KB after every new CODEX pipeline run.
  python knowledge_base/builder.py
  Otherwise the agent's knowledge is stale.
```
