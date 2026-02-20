# AI Customer Support Agent — CLAUDE.md
# Living Architecture Document

> **Purpose:** Single source of truth for this codebase. Update this file whenever you add features, fix bugs, or change architecture decisions.
> **Project path:** `d:/OneDrive - Obeikan Investment Group/desktop/Agents/ai-support-agent/`
> **Last verified working:** February 20, 2026

---

## Quick Status

| Component | Status | Notes |
|---|---|---|
| FastAPI server | ✅ Working | Port 8001 (8000 is taken by another service) |
| SQLite DB | ✅ Working | Auto-created at `./support_agent.db` |
| LangGraph agent | ✅ Working | Uses `create_react_agent` (LangChain 1.x) |
| Groq LLM | ✅ Working | `llama-3.3-70b-versatile` — set `LLM_PROVIDER=groq` |
| Google Gemini | ⚠️ Quota exhausted | Google API key hit free-tier rate limit |
| ChromaDB | ✅ Working | ChromaDB 1.x — persists automatically |
| Embeddings | ✅ Working | `all-MiniLM-L6-v2` via sentence-transformers (CPU) |
| WebSocket chat | ✅ Implemented | `/chat/ws/{tenant_id}/{customer_id}` |
| HTTP chat | ✅ Working | `POST /chat/message` — tested end-to-end |
| Knowledge ingestion | ✅ Implemented | `POST /admin/tenants/{id}/knowledge` |
| Escalation engine | ✅ Working | Keyword + sentiment + turn-count rules |

---

## How to Run

```bash
# Use the correct Python installation (C:/Python312/python.exe)
cd "d:/OneDrive - Obeikan Investment Group/desktop/Agents/ai-support-agent"

# Start the server on port 8001 (port 8000 is occupied by another service)
C:/Python312/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# Test it's running
curl http://localhost:8001/health
# → {"status":"healthy","version":"0.1.0","llm_provider":"groq","database":"sqlite"}

# View API docs
# http://localhost:8001/docs
```

---

## Tech Stack (Actual — Free Tier Build)

| Layer | Technology | Notes |
|---|---|---|
| Web framework | FastAPI + uvicorn | Async, WebSocket support |
| Agent orchestration | LangGraph 1.x `create_react_agent` | REPLACED legacy `AgentExecutor` |
| LLM primary | Groq (`llama-3.3-70b-versatile`) | Free tier, fast inference |
| LLM fallback | Google Gemini (`gemini-2.0-flash`) | ⚠️ Quota currently exhausted |
| Embeddings | `all-MiniLM-L6-v2` via sentence-transformers | Runs locally on CPU, free |
| Vector store | ChromaDB 1.3.5 (local) | Per-tenant collections, auto-persist |
| Database | SQLite via aiosqlite + SQLAlchemy async | File: `./support_agent.db` |
| Session cache | In-memory dict (no Redis) | `_session_cache`, `_message_cache` in session_service.py |
| Escalation queue | In-memory list (no CRM) | `_escalation_queue` in escalation_tools.py |
| Logging | structlog 25.x | `make_filtering_bound_logger("DEBUG")` — no keyword arg |
| Python | 3.12 at `C:/Python312/python.exe` | Multiple Python installations on machine |

---

## File Structure (Actual)

```
ai-support-agent/
├── CLAUDE.md                      ← THIS FILE
├── .env                           ← Active config (LLM_PROVIDER=groq)
├── .env.example
├── requirements.txt               ← Install to C:/Python312/python.exe
├── docker-compose.yml             ← Single container, no Redis/Postgres
├── Dockerfile
├── pyproject.toml
│
├── app/
│   ├── main.py                    ← FastAPI factory + lifespan (init_db)
│   ├── config.py                  ← Pydantic Settings, reads .env
│   ├── dependencies.py            ← get_db_session, AdminAPIKey
│   │
│   ├── api/
│   │   ├── __init__.py            ← Registers health, chat, admin routers
│   │   ├── health.py              ← GET /health, GET /
│   │   ├── chat.py                ← WS /chat/ws/{tenant_id}/{customer_id}
│   │   │                            POST /chat/message
│   │   └── admin.py               ← POST/GET /admin/tenants
│   │                                POST /admin/tenants/{id}/knowledge
│   │                                POST /admin/tenants/{id}/knowledge/upload
│   │
│   ├── agents/
│   │   ├── llm.py                 ← get_llm() — routes to Groq or Google
│   │   ├── base_agent.py          ← BaseAgent using langgraph create_react_agent
│   │   ├── support_agent.py       ← SupportAgent, VoiceAgent, EmailAgent
│   │   │                            get_agent_for_channel() factory
│   │   └── prompts/
│   │       ├── system_prompt.py
│   │       ├── voice_prompt.py
│   │       └── email_prompt.py
│   │
│   ├── tools/
│   │   ├── knowledge_base.py      ← search_knowledge_base @tool
│   │   └── escalation_tools.py    ← escalate_to_human @tool (in-memory queue)
│   │
│   ├── rag/
│   │   ├── embeddings.py          ← get_embedding_model() → HuggingFaceEmbeddings
│   │   ├── vectorstore.py         ← get_vectorstore(tenant_id) → Chroma
│   │   │                            Uses chromadb.PersistentClient (ChromaDB 1.x)
│   │   ├── ingestion.py           ← ingest_documents() — chunk + embed + store
│   │   ├── retriever.py           ← retrieve() — similarity search
│   │   └── loaders.py             ← load_documents() — PDF, URL, text
│   │
│   ├── models/
│   │   ├── base.py                ← SQLAlchemy engine (aiosqlite), init_db()
│   │   ├── tenant.py              ← Tenant ORM model
│   │   ├── session.py             ← ConversationSession ORM model
│   │   ├── message.py             ← Message ORM model
│   │   └── schemas.py             ← Pydantic: ChatRequest, ChatResponse,
│   │                                TenantConfig, TenantCreate, IngestionRequest
│   │
│   ├── services/
│   │   ├── session_service.py     ← SessionService — get/create/history
│   │   │                            In-memory cache (_session_cache, _message_cache)
│   │   └── tenant_service.py      ← TenantService — CRUD + config
│   │
│   ├── escalation/
│   │   └── engine.py              ← EscalationEngine — keyword+sentiment+turns
│   │
│   └── core/
│       ├── logging.py             ← structlog configured logger
│       ├── security.py            ← verify_token, AdminAPIKey
│       ├── guardrails.py          ← PII redaction, topic filtering
│       └── exceptions.py          ← Custom exceptions
│
└── tests/
    ├── conftest.py
    ├── unit/
    │   ├── test_escalation.py
    │   └── test_guardrails.py
    └── integration/
        └── test_api.py
```

---

## Key API Endpoints

```
GET  /                          → {"name": "AI Customer Support Agent", "status": "running"}
GET  /health                    → {"status": "healthy", "llm_provider": "groq", ...}
GET  /docs                      → Swagger UI

POST /admin/tenants             → Create tenant (returns api_key — show only once!)
GET  /admin/tenants             → List all tenants
GET  /admin/tenants/{id}        → Get tenant
PUT  /admin/tenants/{id}/config → Update tenant config (requires api_key header)

POST /admin/tenants/{id}/knowledge         → Ingest from JSON sources array
POST /admin/tenants/{id}/knowledge/upload  → Upload PDF/text files
POST /admin/tenants/{id}/knowledge/text    → Quick text ingestion

POST /chat/message              → HTTP chat (synchronous, good for testing)
WS   /chat/ws/{tenant_id}/{customer_id}?token=xxx  → WebSocket chat (streaming)
```

---

## LLM Provider Configuration

Set `LLM_PROVIDER` in `.env`:

```bash
# Option A: Groq (RECOMMENDED — free, fast)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...

# Option B: Google Gemini (free tier available)
LLM_PROVIDER=google
GOOGLE_API_KEY=AIza...
# ⚠️ Model must be: gemini-2.0-flash (NOT gemini-1.5-pro — deprecated)
```

**Model routing in `app/agents/llm.py`:**
- Groq → `llama-3.3-70b-versatile`
- Google → `gemini-2.0-flash`

---

## Known Bugs Fixed

| Bug | File | Fix Applied |
|---|---|---|
| `AgentExecutor` removed in LangChain 1.x | `app/agents/base_agent.py` | Replaced with `langgraph.prebuilt.create_react_agent` |
| `langchain.text_splitter` removed | `app/rag/ingestion.py` | Changed to `langchain_text_splitters` |
| `structlog.make_filtering_bound_logger(logging_level=...)` → kwarg removed | `app/core/logging.py` | Changed to positional: `make_filtering_bound_logger("DEBUG")` |
| ChromaDB old API (`chroma_db_impl`, `persist()`) removed in 1.x | `app/rag/vectorstore.py`, `ingestion.py` | Use `chromadb.PersistentClient()`, removed `.persist()` call |
| `gemini-1.5-pro` model deprecated/removed | `app/agents/llm.py` | Updated to `gemini-2.0-flash` |

---

## Python Installation Note

This machine has multiple Python installations:
- `C:/Python312/python.exe` ← **USE THIS ONE** (has all project packages installed)
- `C:/Users/.../Programs/Python/Python312/python.exe` ← Different packages
- `C:/Users/.../Programs/Python/Python311/python.exe`

Always use `C:/Python312/python.exe` or `C:/Python312/pip.exe` to install packages.

Port 8000 is occupied by another service. **Always use port 8001** for this project.

---

## Agent Architecture (LangChain 1.x Pattern)

```python
# Old (broken — LangChain < 0.3):
from langchain.agents import AgentExecutor, create_tool_calling_agent
executor = AgentExecutor(agent=agent, tools=tools, ...)
result = await executor.ainvoke({"input": text, "chat_history": history})
output = result["output"]

# New (working — LangChain 1.x / LangGraph):
from langgraph.prebuilt import create_react_agent
graph = create_react_agent(model=llm, tools=tools, prompt=SystemMessage(content=...))
result = await graph.ainvoke({"messages": history + [HumanMessage(content=text)]})
output = result["messages"][-1].content  # last AIMessage
```

The `BaseAgent._build_graph()` implements this. `invoke()` returns `{"output": str, "messages": list}`.

---

## Data Flow — Chat Message

```
POST /chat/message
  → SessionService.get_or_create_session()  → SQLite
  → TenantService.get_config()              → SQLite (or default TenantConfig)
  → get_agent_for_channel("chat", config, tenant_id)
  → SessionService.get_history()            → in-memory cache or SQLite
  → agent.invoke(message, history)
      → LangGraph create_react_agent
          → LLM (Groq/Gemini)
          → if tool call: search_knowledge_base(query, tenant_id)
              → ChromaDB similarity_search()
          → if tool call: escalate_to_human(session_id, reason, urgency)
              → in-memory _escalation_queue
      → returns {"output": str}
  → SessionService.add_message()            → SQLite + cache
  → ChatResponse(session_id, message, escalated, sources)
```

---

## Tenant Model

```python
# Tenant config stored as JSON in SQLite:
{
    "persona_name": "Aria",
    "persona_description": "Friendly AI support agent",
    "escalation_keywords": [],          # empty = use defaults
    "max_turns_before_escalate": 10,
    "channels": ["chat"],
    "language": "en",
    "sentiment_threshold": -0.7,        # escalate if sentiment < this
}
```

Tenants are isolated: each gets their own ChromaDB collection `tenant_{tenant_id}`.

---

## What's NOT Implemented Yet

| Feature | Status | Priority |
|---|---|---|
| Voice pipeline (Twilio + Deepgram + ElevenLabs) | ❌ Missing | Future |
| Email channel (SendGrid inbound parse) | ❌ Missing | Future |
| CRM integrations (Salesforce, Zendesk) | ❌ Missing | Future |
| Redis session cache | ❌ Using in-memory | Needed for multi-process |
| Celery async task queue | ❌ Missing | Needed for large ingestion |
| Alembic DB migrations | ❌ Using auto-create | Add before production |
| Analytics service | ❌ Missing | Future |
| `app/channels/chat_session.py` | ❌ Missing | Future |
| `app/escalation/handoff.py` | ❌ Missing | Future |
| `app/tools/crm_tools.py` | ❌ Missing | Future |
| `app/tools/order_tools.py` | ❌ Missing | Future |
| Authentication (JWT) | ⚠️ Skeleton only | Need to wire in |

---

## Testing

```bash
# Unit tests
C:/Python312/python.exe -m pytest tests/unit/ -v

# Integration tests (requires server running on 8001)
C:/Python312/python.exe -m pytest tests/integration/ -v

# Quick manual test
curl -X POST http://localhost:8001/admin/tenants \
  -H "Content-Type: application/json" \
  -d '{"name":"Acme","slug":"acme","persona_name":"Aria","persona_description":"Support agent","channels":["chat"]}'

curl -X POST http://localhost:8001/chat/message \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"acme","customer_id":"user-1","message":"Hello!"}'
```

---

## Environment Variables (`.env`)

```bash
APP_ENV=development
APP_SECRET_KEY=changeme-use-a-real-secret-key

# LLM Provider
LLM_PROVIDER=groq                          # groq | google
GROQ_API_KEY=gsk_...
GOOGLE_API_KEY=AIza...

# Storage
DATABASE_URL=sqlite+aiosqlite:///./support_agent.db
CHROMA_PERSIST_DIRECTORY=./chroma_data
EMBEDDING_MODEL=all-MiniLM-L6-v2

# App
APP_DOMAIN=localhost:8001
DEBUG=true
```

---

*Update this file whenever you change something significant. It is the memory of this project.*
