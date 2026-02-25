# AI Support Agent Interview Deep Dive

This file is your personal walkthrough for the interview.
It explains:
- which class and method is called
- in what order
- for chat, voice, and email separately
- what automation loops run in the background
- what ChromaDB input/output looks like

---

## 1. First: Understand There Are 2 Agent Paths In This Repo

Your project currently has **two valid flows**:

1. **LangGraph multi-tenant path** (`app/agents/*`)
- Main routes: `/chat/message`, `/chat/ws/{tenant_id}/{customer_id}`, `/chat/email/send`
- Uses SQLAlchemy session storage + LangGraph ReAct tools.

2. **Spec/demo path** (`app/agent/*`)
- Main routes: `/api/chat`, `/ws/chat/{session_id}`, `/api/voice/*`
- Uses in-memory session + simple RAG + optional Groq direct client.

In interview, say this clearly:
"I keep a production-style multi-tenant LangGraph path and a spec-aligned demo path side-by-side for rapid enterprise demos."

---

## 2. App Startup Lifecycle (What Runs First)

### Entry point
File: `app/main.py`

Order:
1. FastAPI app is created (`create_app()`).
2. Routers are attached (`app.include_router(api_router)`).
3. On startup (`lifespan`):
- `init_db()` runs (creates DB tables).
- if `ENABLE_EMAIL_POLLER=true`, starts background loop `_email_poll_loop()`.

### Background email loop
Code path:
- `app.main._email_poll_loop()`
- calls `await app.channels.email_handler.poll_inbox_async()`
- sleeps `EMAIL_POLL_INTERVAL_SECONDS`
- repeats forever while app is alive

This is one of your key "automation cycles".

---

## 3. Route Map (What Endpoint Hits What)

From `app/api/__init__.py`:

- `/chat/*` -> `app/api/chat.py` (LangGraph path)
- `/admin/*` -> tenant/admin tools
- `/api/chat` + `/ws/chat/{session_id}` -> `app/api/demo.py` (spec path)
- `/api/voice/incoming`, `/api/voice/transcribed` -> `app/channels/voice.py`

---

## 4. Chat Flow A: LangGraph Multi-Tenant Path

Endpoint: `POST /chat/message`
File: `app/api/chat.py`, method: `send_message(...)`

### Exact call sequence
1. `SessionService.get_or_create_session(...)`
2. `TenantService.get_config(...)`
3. `get_agent_for_channel(channel="chat", ...)` from `app/agents/support_agent.py`
4. `SessionService.add_message(... role="user")`
5. `SessionService.get_history(...)`
6. `agent.invoke(user_input, history)` -> this is `BaseAgent.invoke(...)`
7. `SessionService.add_message(... role="assistant")`
8. `EscalationEngine.should_escalate(...)` from `app/agents/escalation_engine.py`
9. if needed: `_perform_escalation(...)` from `app/tools/escalation_tools.py`
10. return `ChatResponse`

### What happens inside `BaseAgent.invoke(...)`
File: `app/agents/base_agent.py`

1. Builds message list (`history + HumanMessage(user_input)`)
2. Calls compiled LangGraph agent:
- `self._graph.ainvoke({"messages": messages}, config={"recursion_limit": 4})`
3. Extracts final AI text from returned messages
4. Cleans tool-call artifacts
5. Returns `{"output": "...", "messages": [...] }`

### How tools are connected
File: `app/agents/support_agent.py`

`_get_tools()` returns:
- `make_search_tool(self.tenant_id)` -> KB retrieval tool
- `escalate_to_human` -> escalation tool

So the LLM can call tools during reasoning.

---

## 5. Chat Flow B: Spec/Demo Path

Endpoint: `POST /api/chat`
File: `app/api/demo.py`, method: `chat_rest(payload)`

### Exact call sequence
1. `_session_manager.get_or_create(session_id, channel="chat")` from `app/storage/session.py`
2. `_session_manager.add_message(... role="user")`
3. `_get_agent().respond(message, session)` from `app/agent/support_agent.py`
4. `_session_manager.add_message(... role="agent")`
5. Return JSON with:
- `message`, `intent`, `confidence`, `escalated`, `sources`, `ticket`

### What happens in `SupportAgent.respond(...)`
File: `app/agent/support_agent.py`

1. `self.rag.search(...)`
2. Format KB context string
3. Generate answer:
- if Groq key exists -> LLM call
- else -> deterministic fallback response
4. `self.escalate.should_escalate(...)`
5. if escalation/unsure -> `self.tools.create_ticket(...)`
6. Return `AgentResponse`

---

## 6. WebSocket Chat Loops (Two Separate Loops)

### A) LangGraph WS
Endpoint: `/chat/ws/{tenant_id}/{customer_id}`
Method: `chat_websocket(...)` in `app/api/chat.py`

Loop:
`while True`:
- receive JSON
- save user message
- get history
- call `agent.invoke(...)`
- evaluate escalation
- send response frame + done frame
- save assistant message

Break condition:
- client disconnects or websocket closes.

### B) Spec WS
Endpoint: `/ws/chat/{session_id}`
Method: `chat_websocket_handler(...)` in `app/channels/chat.py`

Loop:
`while True`:
- receive JSON `{message: ...}`
- call `SupportAgent.respond(...)`
- send JSON result
- if `response.escalate` true -> send escalation message then `break`

---

## 7. Voice Flow (Twilio)

File: `app/channels/voice.py`

### Route 1: call arrives
`POST /api/voice/incoming` -> `handle_incoming_call(...)`

Returns TwiML:
- `<Say>` greeting
- `<Gather input="speech" action="/api/voice/transcribed">`

### Route 2: transcription callback
`POST /api/voice/transcribed` -> `handle_transcription(...)`

Sequence:
1. Parse Twilio form fields:
- `SpeechResult`
- `CallSid`
2. `SessionManager.get_or_create(CallSid, "voice")`
3. `SupportAgent.respond(...)`
4. sanitize text for XML
5. return TwiML:
- normal: reply + another `<Gather>` (continue loop)
- escalated: reply + human handoff message

So voice continuity is not a Python while-loop; Twilio callbacks create a loop across HTTP requests.

---

## 8. Email Flow (Two Modes)

### Mode A: API-triggered email drafting
Endpoint: `POST /chat/email/send`
Method: `send_email_endpoint(...)` in `app/api/chat.py`

Sequence:
1. Build combined message `Subject + Body`
2. Agent invocation (email channel prompt style)
3. Escalation evaluation
4. `_send_reply(...)` SMTP send
5. return response JSON

### Mode B: Automated polling loop
File: `app/channels/email_handler.py`
Method: `poll_inbox_async()`

Sequence:
1. Connect IMAP (`imap.gmail.com`)
2. Read UNSEEN emails
3. For each email:
- parse sender/subject/body
- create/get session
- `SupportAgent.respond(...)`
- `_send_reply(...)` via SMTP
- mark as seen

This is another key automation cycle.

---

## 9. Escalation Layer (Rules Before Fancy AI)

You have two escalation engines:

1. `app/agents/escalation_engine.py` (LangGraph path)
2. `app/agent/escalation.py` (spec path)

Both are rules-first:
- safety keywords -> immediate escalate
- user requests human -> escalate
- model uncertainty -> escalate
- too many turns -> escalate

Interview message:
"I do deterministic escalation first for safety and reliability; LLM confidence is secondary."

---

## 10. RAG + ChromaDB: What Actually Happens

### Ingestion

LangGraph side:
- `app/rag/ingestion.py` loads docs
- splits into chunks
- `vectorstore.add_documents(chunks)` into Chroma collection `tenant_{tenant_id}`

Spec side:
- `app/knowledge_base/builder.py`
- loops alarm records
- `RAGPipeline.add_record(record_id, text, metadata)`
- stores in collection `support_kb`

### Query path

LangGraph side:
- `make_search_tool(...)` -> `retrieve(...)` -> `vectorstore.similarity_search(...)`

Spec side:
- `SupportAgent.respond(...)` -> `RAGPipeline.search(...)`
- returns `KBSearchResult[]`

### Raw Chroma query output shape (spec path)

`RAGPipeline.search()` internally receives object like:

```json
{
  "ids": [["KHS_Filler_282", "KHS_Filler_9093"]],
  "documents": [["Alarm 282 ... Action: ...", "Alarm 9093 ... Action: ..."]],
  "metadatas": [[
    {
      "alarm_id": "282",
      "description": "Hydraulic pressure low",
      "cause": "Pump wear",
      "action": "Inspect pump and replace seal",
      "machine": "KHS_Filler"
    },
    {
      "alarm_id": "9093",
      "description": "Motor overload",
      "cause": "Bearing friction",
      "action": "Stop line and inspect bearing",
      "machine": "KHS_Filler"
    }
  ]],
  "distances": [[0.11, 0.24]]
}
```

Then your code converts each row to:

```json
{
  "alarm_id": "282",
  "description": "Hydraulic pressure low",
  "cause": "Pump wear",
  "action": "Inspect pump and replace seal",
  "machine": "KHS_Filler",
  "score": 0.89
}
```

(`score = 1 - distance`)

---

## 11. Response Payload Samples (What UI Gets)

### Sample `/api/chat` response (spec path)

```json
{
  "message": "What this alarm means: Alarm 282 indicates hydraulic pressure deviation.\nLikely cause: Pump wear or seal leakage.\nWhat to do: 1) Inspect pump pressure. 2) Replace faulty seal. 3) Restart and verify alarm reset.",
  "intent": "fault_lookup",
  "confidence": 0.89,
  "escalated": false,
  "sources": [
    "Hydraulic pressure low on filler module"
  ],
  "ticket": null
}
```

### Sample `/api/chat` when escalation is triggered

```json
{
  "message": "This sounds safety-critical. I will escalate to a human engineer now.",
  "intent": "escalate",
  "confidence": 0.31,
  "escalated": true,
  "sources": [],
  "ticket": {
    "ticket_id": "TKT-A1B2C3D4",
    "session_id": "demo-seq-2",
    "channel": "chat",
    "summary": "Emergency: smoke near filler line",
    "machine": "KHS_Filler",
    "alarm_code": null,
    "priority": "medium",
    "status": "open",
    "created_at": "2026-02-25T10:10:00Z"
  }
}
```

### Sample voice TwiML response

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">What this alarm means ...</Say>
  <Gather input="speech" action="/api/voice/transcribed" speechTimeout="auto">
    <Say voice="Polly.Joanna">Is there anything else I can help you with?</Say>
  </Gather>
</Response>
```

---

## 12. What "LangGraph" Means Here (Simple Version)

In this repo, LangGraph is the runtime that:
1. takes your message + history
2. lets the model decide if it should call tools
3. executes tools (KB search/escalation)
4. feeds tool results back to model
5. returns final answer
6. stops at recursion limit (`4`) so loops do not run forever

That is the "agent orchestration loop".

---

## 13. Interview Script (Short, Strong Answer)

Use this when asked "walk me through your system":

"A request enters through chat, voice, or email.  
The channel adapter normalizes it to text and attaches session context.  
Then the orchestration layer selects the channel-specific agent and retrieves recent history.  
The agent runs a RAG lookup in ChromaDB and can call escalation tools through LangGraph when needed.  
A rules-first escalation engine checks safety terms, explicit human requests, uncertainty, and turn limits.  
If unresolved, we create a ticket and hand off.  
Finally, the channel renderer formats output as JSON, TwiML, or SMTP email.  
In parallel, a background email polling loop continuously processes new emails."

---

## 14. Last-Minute Cheat Sheet (Class -> Method)

- App bootstrap:
  - `app.main.create_app`
  - `app.main.lifespan`
- LangGraph chat:
  - `app.api.chat.send_message`
  - `app.agents.base_agent.invoke`
  - `app.tools.knowledge_base.make_search_tool`
  - `app.tools.escalation_tools._perform_escalation`
- Spec chat:
  - `app.api.demo.chat_rest`
  - `app.agent.support_agent.respond`
  - `app.agent.rag_pipeline.search`
  - `app.agent.tools.create_ticket`
- Voice:
  - `app.channels.voice.handle_incoming_call`
  - `app.channels.voice.handle_transcription`
- Email:
  - `app.api.chat.send_email_endpoint`
  - `app.channels.email_handler.poll_inbox_async`
  - `app.channels.email_handler._send_reply`

---

## 15. Important Note for Interview Honesty

You can say:
"I am comfortable building and debugging LangGraph-based pipelines, and I can explain the full execution path end-to-end. I am still deepening advanced LangGraph internals, but I already use it in production-like flows with tool calling, guardrails, and escalation."

This is honest, strong, and credible.

