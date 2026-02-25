# Interview File 2: Full App Architecture + Exact Call Order

This file explains your app exactly as implemented: classes, methods, routes, and execution order.

---

## 1. Top-Level Architecture

Your app has two parallel stacks.

## Stack A: Multi-tenant LangGraph Stack
- Routes: `/chat/*`, `/admin/*`
- Agent runtime: `app/agents/*`
- Storage: SQLAlchemy models + session service
- Tools: LangChain/LangGraph tool-calling

## Stack B: Spec Demo Stack
- Routes: `/api/chat`, `/ws/chat/{session_id}`, `/api/voice/*`
- Agent runtime: `app/agent/*`
- Storage: in-memory session + optional Mongo fallback

Both are valid. This is important to explain clearly in interview.

---

## 2. Boot Sequence

Entry:
- [app/main.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\main.py)

Order:
1. `create_app()`
2. CORS middleware attached
3. Routers included (`api_router`)
4. Lifespan startup:
   - `init_db()`
   - optional `_email_poll_loop()` task
5. App waits for requests

---

## 3. Router Wiring Map

Router file:
- [app/api/__init__.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\api\__init__.py)

Map:
1. `health_router` -> `/health`
2. `chat_router` -> `/chat/*`
3. `admin_router` -> `/admin/*`
4. `demo_router` -> `/api/chat`, `/ws/chat/{session_id}`
5. `voice_router` -> `/api/voice/*`

---

## 4. Chat Flow (LangGraph HTTP)

Endpoint:
- `POST /chat/message`
- Method: `send_message(...)`
- File: [app/api/chat.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\api\chat.py)

Exact call order:
1. `SessionService.get_or_create_session(...)`
2. `TenantService.get_config(...)`
3. `get_agent_for_channel(channel="chat", ...)`
4. `SessionService.add_message(role="user")`
5. `SessionService.get_history(...)`
6. `agent.invoke(user_input, history)`
7. `SessionService.add_message(role="assistant")`
8. `EscalationEngine.should_escalate(...)`
9. optional `_perform_escalation(...)`
10. return `ChatResponse`

---

## 5. Chat Flow (LangGraph WebSocket)

Endpoint:
- `WS /chat/ws/{tenant_id}/{customer_id}`
- Method: `chat_websocket(...)`

Loop:
1. receive JSON
2. save user message
3. load history
4. `agent.invoke(...)`
5. run escalation check
6. send response frame
7. send done frame
8. persist assistant
9. repeat

Break:
- disconnect or close

---

## 6. What Happens Inside `agent.invoke(...)`

File:
- [app/agents/base_agent.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\agents\base_agent.py)

Key internals:
1. Convert `history + new user message` to LangChain messages
2. Execute compiled graph:
   - `self._graph.ainvoke(...)`
3. Graph created by:
   - `create_react_agent(model, tools, prompt)`
4. Tool calls can happen during graph run
5. Final AI output extracted and cleaned

Control:
- `_GRAPH_CONFIG = {"recursion_limit": 4}` prevents infinite loops

---

## 7. Tool Path (LangGraph Stack)

Tool sources:
- [app/tools/knowledge_base.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\tools\knowledge_base.py)
- [app/tools/escalation_tools.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\tools\escalation_tools.py)

How attached:
- [app/agents/support_agent.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\agents\support_agent.py) `_get_tools()`

KB tool chain:
1. tool called with `query`
2. `retrieve(query, tenant_id, k=4)` from `app/rag/retriever.py`
3. `vectorstore.similarity_search(...)`
4. return formatted source blocks

Escalation tool chain:
1. tool called with `reason`, `urgency`
2. `_perform_escalation(...)`
3. queue escalation + ticket id
4. return customer-safe handoff text

---

## 8. Chat Flow (Spec Demo HTTP)

Endpoint:
- `POST /api/chat`
- Method: `chat_rest(payload)`
- File: [app/api/demo.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\api\demo.py)

Order:
1. `SessionManager.get_or_create(session_id, "chat")`
2. optionally attach `machine`
3. save user message
4. `SupportAgent.respond(message, session)`
5. save agent message
6. return `message, intent, confidence, escalated, sources, ticket`

---

## 9. Spec `SupportAgent.respond(...)` Internals

File:
- [app/agent/support_agent.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\agent\support_agent.py)

Order:
1. `self.rag.search(...)`
2. `_format_kb_context(...)`
3. `_generate_response(...)`
   - if Groq configured: API completion
   - else: fallback deterministic response
4. confidence score from top hit
5. `self.escalate.should_escalate(...)`
6. ticket creation if escalation/uncertainty
7. return `AgentResponse`

---

## 10. Voice Call Order

File:
- [app/channels/voice.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\channels\voice.py)

Route A:
1. `POST /api/voice/incoming`
2. returns TwiML with `<Say>` + `<Gather>`

Route B:
1. `POST /api/voice/transcribed`
2. parse `SpeechResult`, `CallSid`
3. `SessionManager.get_or_create(CallSid, "voice")`
4. `SupportAgent.respond(...)`
5. return TwiML:
   - continue gather loop
   - or escalation handoff message

Important:
Voice loop is callback-driven by Twilio webhooks, not a Python while-loop.

---

## 11. Email Call Order

File:
- [app/channels/email_handler.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\channels\email_handler.py)

Polling cycle in `poll_inbox_async()`:
1. read env creds
2. IMAP login + inbox select
3. search unseen
4. for each unseen message:
   - parse sender/subject/body
   - session lookup/create
   - `SupportAgent.respond(...)`
   - `_send_reply(...)` via SMTP
   - mark seen
5. logout

Scheduled by:
- `app/main.py` `_email_poll_loop()`

---

## 12. State and Storage Layers

## SQL stack (LangGraph path)
- Session/message persistence via SQLAlchemy
- files:
  - `app/models/session.py`
  - `app/models/message.py`
  - `app/services/session_service.py`

## In-memory spec stack
- `app/storage/session.py`
- `app/models/agent_models.py`

## DB abstraction for spec stack
- `app/storage/database.py`
- uses Mongo if configured; otherwise in-memory fallback

---

## 13. Escalation Decision Layers

LangGraph route checks:
- `app/agents/escalation_engine.py`

Spec route checks:
- `app/agent/escalation.py`

Rules used in both styles:
1. safety keywords
2. explicit human request
3. model uncertainty
4. turn-limit/low-confidence gates

---

## 14. LLM Provider Layer

File:
- [app/agents/llm.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\agents\llm.py)

Provider selection:
1. `LLM_PROVIDER=groq` -> `ChatGroq`
2. `LLM_PROVIDER=google` -> `ChatGoogleGenerativeAI`

This affects LangGraph stack.  
Spec stack uses direct Groq client if `GROQ_API_KEY` exists, else fallback text logic.

---

## 15. Interview Summary Sentence

"This system separates channel adapters (chat/voice/email), orchestration and memory, agent/tool execution, and retrieval storage. The LangGraph stack handles multi-tenant production-style workflows, while the spec stack gives fast deterministic demos with the same escalation and RAG behavior."

