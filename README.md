# AI Customer Support Agent —  Industrial Platform

> **A multi-tenant, multi-channel AI support platform — answers customer queries across Chat, Voice, and Email using a RAG knowledge base, automatically escalates when it needs a human, and wires into n8n for downstream automation.**

---

## What Does This App Do?

| Feature | What You Can Do |
|---|---|
| **Multi-Channel** | Customers can reach the agent via Chat (WebSocket or HTTP), Voice (Twilio phone call), or Email — all using the same underlying AI |
| **RAG Knowledge Base** | Upload PDFs, URLs, or plain text — the agent searches this knowledge base to answer questions accurately instead of guessing |
| **Multi-Tenant** | One platform serves many companies. Each tenant has its own isolated knowledge base, custom AI persona name, escalation rules, and language |
| **Automatic Escalation** | The agent detects when it should hand off to a human — based on keywords ("speak to a human", "manager"), negative sentiment, agent uncertainty, or too many unresolved turns |
| **n8n Automation** | When escalation triggers, n8n fires: Slack notifications, Zendesk ticket creation, CRM updates — all without writing custom integration code |
| **Live Demo UI** | A browser-based chat demo is served at the root URL. No frontend build step needed |
| **Advanced CSV Extraction** | Upload a machine manual PDF — the system extracts structured alarm codes into a downloadable CSV and ingests them into the knowledge base |

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                          Clients / Channels                          │
│                                                                      │
│   Browser (Chat)     Twilio (Voice Call)     Email Client (SMTP)     │
└──────────┬───────────────────┬────────────────────────┬─────────────┘
           │ WebSocket / HTTP  │ TwiML Webhook          │ SMTP / HTTP
           │                   │                        │
           ▼                   ▼                        ▼
┌──────────────────────────────────────────────────────────────────────┐
│                   FastAPI Backend  (Port 8001)                        │
│                                                                      │
│  ┌────────────┐  ┌──────────────┐  ┌─────────────┐  ┌────────────┐  │
│  │ /chat/ws   │  │ /api/voice   │  │ /chat/email │  │  /admin    │  │
│  │ /chat/msg  │  │  (Twilio)    │  │   /send     │  │  /tenants  │  │
│  └─────┬──────┘  └──────┬───────┘  └──────┬──────┘  └─────┬──────┘  │
│        │                │                 │                │         │
│        └────────────────┴─────────────────┘                │         │
│                         │                                  │         │
│                         ▼                                  ▼         │
│  ┌──────────────────────────────────────┐  ┌────────────────────────┐│
│  │         Channel Router               │  │    Admin / Ingestion   ││
│  │  channel → agent class factory       │  │  Tenant CRUD           ││
│  │  SupportAgent │ VoiceAgent │         │  │  Knowledge Upload      ││
│  │  EmailAgent                          │  │  CSV Extraction        ││
│  └──────────────────────┬───────────────┘  └────────────────────────┘│
│                         │                                             │
│                         ▼                                             │
│  ┌────────────────────────────────────────────────────────────────┐   │
│  │              LangChain Agent  (Groq Llama 3.3-70b)             │   │
│  │                                                                │   │
│  │   System Prompt (tenant persona)                               │   │
│  │   + Conversation History                                       │   │
│  │   + Tool Calls:                                                │   │
│  │       ① search_knowledge_base  → ChromaDB semantic search      │   │
│  │       ② escalate_to_human      → EscalationEngine              │   │
│  └──────────────────────────┬─────────────────────────────────────┘   │
│                             │                                          │
│           ┌─────────────────┴──────────────────┐                      │
│           ▼                                    ▼                      │
│  ┌────────────────────┐         ┌──────────────────────────────────┐  │
│  │  EscalationEngine  │         │         RAG Pipeline              │  │
│  │                    │         │                                   │  │
│  │  keyword rules     │         │  Query → Embed (all-MiniLM-L6-v2) │  │
│  │  sentiment score   │         │       → ChromaDB cosine search    │  │
│  │  human requests    │         │       → top-k context chunks      │  │
│  │  agent uncertainty │         │  (per-tenant isolated collection) │  │
│  │  turn count limit  │         └──────────────────────────────────┘  │
│  └────────────┬───────┘                                               │
│               │                                                       │
│               ▼                                                       │
│  ┌────────────────────┐                                               │
│  │  n8n Client        │                                               │
│  │  POST /webhook/    │                                               │
│  │  ai-agent-         │                                               │
│  │  escalation        │                                               │
│  └────────────────────┘                                               │
└──────────────────────────────────────────────────────────────────────┘
           │                         │
           ▼                         ▼
┌─────────────────────┐   ┌─────────────────────────────────────────┐
│  SQLite (aiosqlite) │   │  ChromaDB (local disk)                   │
│  Sessions           │   │  One collection per tenant:              │
│  Messages           │   │  "tenant_{slug}" → vectors + metadata    │
│  Tenants            │   └─────────────────────────────────────────┘
└─────────────────────┘
           │
           ▼
┌──────────────────────────────────────────────────────────────────────┐
│                 n8n  (localhost:5678)                                 │
│  Escalation webhook → Slack / Zendesk / CRM / Email notifications    │
└──────────────────────────────────────────────────────────────────────┘
```

---

## The Four Pipelines

### Pipeline 1 — Knowledge Base Ingestion

Documents are loaded, chunked, embedded, and stored per tenant so the agent always searches the right knowledge base.

```
Admin uploads PDF / URL / plain text
             │
             ▼
1. load_documents()
   ├── PDF  → pypdf page-by-page extraction
   ├── URL  → BeautifulSoup HTML scraper
   └── Text → passed through directly
             │
             ▼
2. RecursiveCharacterTextSplitter
   chunk_size=800 tokens, overlap=100 tokens
   (overlap prevents losing sentences at chunk boundaries)
             │
             ▼
3. Add tenant_id to every chunk's metadata
   (ensures isolation — one tenant cannot retrieve another's documents)
             │
             ▼
4. Embed each chunk with sentence-transformers
   Model: all-MiniLM-L6-v2  (runs locally, no API key)
   Produces: 384-dim dense vector per chunk
             │
             ▼
5. Store in ChromaDB collection: "tenant_{slug}"
   Persisted to disk at ./chroma_data
   Upsert — same source ingested again is deduplicated by chunk ID
             │
             ▼
   "N chunks indexed and searchable"
```

---

### Pipeline 2 — Chat Pipeline (WebSocket or HTTP)

This is the main conversation loop. Every customer message flows through this path.

```
Customer sends message
             │
             ▼
1. Get or create Session (SQLite)
   session_id | tenant_id | customer_id | channel | turn_count
             │
             ▼
2. Load conversation history from DB
   Last N messages (HumanMessage / AIMessage pairs)
             │
             ▼
3. TenantService.get_config(tenant_id)
   → persona_name, escalation_keywords, language, max_turns, ...
             │
             ▼
4. get_agent_for_channel(channel, tenant_config, tenant_id)
   ├── "chat"  → SupportAgent  (full responses)
   ├── "voice" → VoiceAgent    (short, TTS-friendly)
   └── "email" → EmailAgent    (long, formatted, professional)
             │
             ▼
5. LangChain ReAct Agent invoked (Groq llama-3.3-70b)
   System prompt: tenant persona + channel instructions
   History: last N turns
   Tools available:
     ① search_knowledge_base(query)
        → embed query → ChromaDB cosine search (tenant's collection only)
        → return top-k document chunks as context
     ② escalate_to_human(reason, urgency)
        → model calls this tool if it decides to escalate
             │
             ▼
6. LLM ReAct loop:
   THINK → call tool → observe result → THINK → final answer
   (Capped at 45-second timeout)
             │
             ▼
7. EscalationEngine.evaluate()
   Checks independently of the LLM:
   ├── Custom tenant keywords in message?
   ├── "sue" / "manager" in message? (high urgency)
   ├── Safety pattern? (fire, emergency, explosion...)
   ├── Human request pattern? (speak to, transfer...)
   ├── Agent response contains uncertainty signals?
   ├── Sentiment score below threshold?
   └── Turn count exceeds max_turns?
             │
             ▼
8. If escalated → _perform_escalation()
   → creates a ticket record
   → notifies n8n via POST /webhook/ai-agent-escalation
   → n8n fires Slack / Zendesk / CRM actions
             │
             ▼
9. Persist assistant message + latency_ms to DB
             │
             ▼
10. Return response to client
    { message, escalated, intent, session_id }
```

---

### Pipeline 3 — Voice Pipeline (Twilio)

Phone calls go through Twilio. The agent speaks back via Amazon Polly TTS, integrated into Twilio's TwiML format.

```
Customer dials a Twilio phone number
             │
             ▼
1. Twilio calls POST /api/voice/incoming
   Agent plays greeting via Amazon Polly (Polly.Joanna voice)
   Twilio listens for speech input
             │
             ▼
2. Customer speaks → Twilio transcribes speech → SpeechResult
   Twilio calls POST /api/voice/transcribed with the text
             │
             ▼
3. SessionManager.get_or_create(CallSid, channel="voice")
   CallSid used as session key
             │
             ▼
4. SupportAgent.respond(message, session)
   Runs full RAG search + Groq LLM (same core as chat)
   VoiceAgent uses a shorter, conversational system prompt
             │
             ▼
5. EscalationEngine checks response
   If escalated:
     TwiML: speak answer + "Connecting you to a human engineer. Please hold."
   If not escalated:
     TwiML: speak answer + "Is there anything else I can help you with?" + Gather
             │
             ▼
6. Twilio reads TwiML, speaks it via Polly, waits for next input
   → Loop back to step 2 until call ends or escalation
```

---

### Pipeline 4 — Escalation & n8n Automation Pipeline

This pipeline describes what happens the moment the EscalationEngine fires — from detection to downstream action.

```
Escalation triggered (from any channel)
             │
             ▼
1. EscalationEngine.evaluate() returns:
   EscalationResult {
     should_escalate: true,
     reason: "keyword_match:manager" | "negative_sentiment" | "max_turns_exceeded" | ...,
     urgency: "high" | "medium" | "low"
   }
             │
             ▼
2. _perform_escalation(session_id, reason, urgency)
   Creates a ticket record
   Gathers: session_id, tenant_id, customer message, channel, timestamp
             │
             ▼
3. n8n Client fires POST /webhook/ai-agent-escalation
   Payload: {
     event: "escalation",
     ticket_id, session_id, reason, urgency,
     customer_message, tenant_id, agent_source
   }
             │
             ▼
4. n8n Workflow executes (runs at localhost:5678):
   ┌─────────────────────────────────────────────────┐
   │  Webhook trigger                                │
   │      ↓                                          │
   │  Route by urgency:                              │
   │    high   → Slack #urgent-escalations + PagerDuty│
   │    medium → Slack #support-escalations           │
   │    low    → Email to support queue               │
   │      ↓                                          │
   │  Create Zendesk ticket                          │
   │      ↓                                          │
   │  Tag customer in CRM (HubSpot / Salesforce)     │
   └─────────────────────────────────────────────────┘
             │
             ▼
5. Response sent back to customer notifying them
   a human will follow up
```

---

## Multi-Tenant Architecture

Every company that uses this platform is a **tenant**. Tenants are completely isolated from each other.

```
┌────────────────────────────────────────────────────────┐
│                   Platform (Single App)                 │
│                                                        │
│  ┌────────────────────┐  ┌────────────────────────┐   │
│  │  Tenant A          │  │  Tenant B               │   │
│  │  slug: "acme"      │  │  slug: "globex"         │   │
│  │  persona: "Aria"   │  │  persona: "Max"         │   │
│  │  language: en      │  │  language: ar           │   │
│  │  channels: [chat]  │  │  channels: [chat,voice] │   │
│  │                    │  │                         │   │
│  │  KB Collection:    │  │  KB Collection:         │   │
│  │  "tenant_acme"     │  │  "tenant_globex"        │   │
│  │  (in ChromaDB)     │  │  (in ChromaDB)          │   │
│  └────────────────────┘  └────────────────────────┘   │
│                                                        │
│  One SQLite DB — tenant-scoped rows via tenant_id      │
│  One ChromaDB dir — separate collection per tenant     │
│  One FastAPI app — per-request tenant resolution       │
└────────────────────────────────────────────────────────┘
```

**What is isolated per tenant:**
- Knowledge base (separate ChromaDB collection)
- AI persona name and description
- Escalation keywords list
- Max turns before escalation
- Sentiment threshold
- Enabled channels (chat / voice / email)
- Language for responses

---

## Agent Class Structure

Three agent types, all inheriting from `BaseAgent`. The factory function picks the right one based on channel.

```
BaseAgent (app/agents/base_agent.py)
│   LangChain LCEL chain
│   invoke(user_input, history) → {output: str}
│   Tools injected at construction time
│
├── SupportAgent  (channel: "chat")
│       system_prompt: full professional responses
│       tools: [search_knowledge_base, escalate_to_human]
│
├── VoiceAgent    (channel: "voice")
│       system_prompt: short, no markdown, TTS-friendly
│       tools: [search_knowledge_base, escalate_to_human]
│
└── EmailAgent    (channel: "email")
        system_prompt: long, well-formatted, professional sign-off
        tools: [search_knowledge_base, escalate_to_human]

get_agent_for_channel(channel, tenant_config, tenant_id)
  → returns the right agent class with tenant_id bound via closure
     (tenant_id never passed to the LLM — injected transparently into tool)
```

---

## Escalation Engine — Decision Logic

```
User message arrives
         │
         ▼
┌────────────────────────────────────────────┐
│  1. Tenant custom keywords                 │  → escalate (medium)
│     (configured per tenant in DB)          │
└────────────────────────────────────────────┘
         │ no match
         ▼
┌────────────────────────────────────────────┐
│  2. High-urgency legal/threat words        │  → escalate (HIGH)
│     "sue", "manager"                       │
└────────────────────────────────────────────┘
         │ no match
         ▼
┌────────────────────────────────────────────┐
│  3. Safety pattern regex                   │  → escalate (medium)
│     fire, smoke, injury, emergency,        │
│     explosion, production stop, shutdown   │
└────────────────────────────────────────────┘
         │ no match
         ▼
┌────────────────────────────────────────────┐
│  4. Human request pattern regex            │  → escalate (low)
│     "speak to", "transfer", "human",       │
│     "agent", "customer service"            │
└────────────────────────────────────────────┘
         │ no match
         ▼
┌────────────────────────────────────────────┐
│  5. Agent uncertainty in response          │  → escalate (low)
│     "don't know", "no information",        │
│     "not in my knowledge base"             │
└────────────────────────────────────────────┘
         │ no match
         ▼
┌────────────────────────────────────────────┐
│  6. Sentiment score < threshold            │  → escalate (medium)
│     keyword scoring: terrible=-0.6,        │
│     angry=-0.5, thank=+0.3, great=+0.4    │
└────────────────────────────────────────────┘
         │ no match
         ▼
┌────────────────────────────────────────────┐
│  7. Turn count > max_turns_before_escalate │  → escalate (low)
│     default: 6 turns (configurable/tenant) │
└────────────────────────────────────────────┘
         │ no match
         ▼
    No escalation → continue conversation
```

---

## Tech Stack

| Layer | Technology | Why |
|---|---|---|
| **Backend** | FastAPI + Uvicorn | Async Python API, WebSocket support, auto Swagger docs |
| **LLM** | Groq `llama-3.3-70b-versatile` | Fast cloud inference, free tier available |
| **LLM Alt** | Google Gemini (`langchain-google-genai`) | Swap with `LLM_PROVIDER=google` |
| **Embeddings** | `sentence-transformers all-MiniLM-L6-v2` | Runs 100% locally, no API key needed |
| **Vector Store** | ChromaDB (local disk) | Per-tenant collections, persistent, no server needed |
| **AI Agent** | LangChain LCEL + ReAct | Tool routing, conversation history, streaming |
| **Session Store** | SQLite + aiosqlite + SQLAlchemy | Async, zero-config, stores sessions and messages |
| **Channels** | Chat (WS/HTTP) · Voice (Twilio) · Email (SMTP) | One agent, three frontends |
| **Automation** | n8n webhooks | Escalation → Slack / Zendesk / CRM without custom code |
| **Validation** | Pydantic v2 | Type-safe request/response schemas |
| **Logging** | structlog | Structured JSON logs |
| **PDF Parsing** | pypdf | Extract text from uploaded manuals |
| **Web Scraping** | BeautifulSoup4 | Load knowledge from URLs |
| **API Docs** | Swagger UI (built-in) | Interactive explorer at `/docs` |
| **Demo UI** | demo.html served at `/` | Browser chat without any frontend build |

---

## How to Run It

### Prerequisites

```
Python 3.11+
A Groq API key (free at console.groq.com)
```

### Step 1 — Clone and Set Up Environment

```powershell
git clone <repo-url>
cd Anti-support-agent
python -m venv venv
venv\Scripts\activate
pip install -e .
```

### Step 2 — Configure `.env`

```env
APP_ENV=development
APP_SECRET_KEY=your-secret-key-here

LLM_PROVIDER=groq
GROQ_API_KEY=gsk_...your-key-here...

DATABASE_URL=sqlite+aiosqlite:///./support_agent.db
CHROMA_PERSIST_DIRECTORY=./chroma_data
EMBEDDING_MODEL=all-MiniLM-L6-v2
```

### Step 3 — Start the Backend

```powershell
venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

App running at `http://localhost:8001`

### Step 4 — Open the Demo

1. Go to `http://localhost:8001` — the chat demo loads automatically
2. Go to `http://localhost:8001/docs` — Swagger UI for the full API

### Step 5 — Create a Tenant and Add Knowledge

```bash
# Create a tenant
curl -X POST http://localhost:8001/admin/tenants \
  -H "Content-Type: application/json" \
  -d '{"name": "My Company", "slug": "myco", "config": {"persona_name": "Aria"}}'

# Upload a PDF to the knowledge base
curl -X POST "http://localhost:8001/admin/tenants/myco/knowledge/upload" \
  -F "files=@machine_manual.pdf"

# Chat with the agent
curl -X POST http://localhost:8001/chat/message \
  -H "Content-Type: application/json" \
  -d '{"tenant_id": "myco", "customer_id": "user1", "message": "What does alarm 3042 mean?"}'
```

---

## API Reference

Interactive docs: **`http://localhost:8001/docs`** (Swagger UI)

| Endpoint | Method | Description |
|---|---|---|
| `/health` | `GET` | Health check — returns LLM provider and DB status |
| `/chat/ws/{tenant_id}/{customer_id}` | `WebSocket` | Real-time chat with persistent connection |
| `/chat/message` | `POST` | Single-turn HTTP chat (no WebSocket needed) |
| `/chat/email/send` | `POST` | Inbound email → agent drafts reply → SMTP dispatch |
| `/admin/tenants` | `POST` | Create a new tenant (returns API key — save it!) |
| `/admin/tenants` | `GET` | List all tenants |
| `/admin/tenants/{id}/config` | `PUT` | Update tenant persona, channels, escalation rules |
| `/admin/tenants/{id}/knowledge` | `POST` | Ingest knowledge from PDF, URL, or text |
| `/admin/tenants/{id}/knowledge/upload` | `POST` | Upload PDF or text files directly |
| `/admin/tenants/{id}/knowledge/advanced_csv_extract` | `POST` | Extract structured alarms from PDF → CSV + RAG |
| `/admin/tenants/{id}/knowledge/text` | `POST` | Add raw text to the knowledge base instantly |
| `/api/voice/incoming` | `POST` | Twilio inbound call webhook (plays greeting) |
| `/api/voice/transcribed` | `POST` | Twilio speech-to-text → agent → TwiML response |
| `/n8n/...` | `POST` | n8n calls back into the agent via these endpoints |

---

## Key Design Decisions

**Why ChromaDB instead of a cloud vector store?**
Local development needs zero external services. ChromaDB persists to disk, creates one collection per tenant automatically, and the same LangChain abstraction would let you swap it to Pinecone or Weaviate in production with one line.

**Why tenant_id is never passed to the LLM?**
The `search_knowledge_base` tool has `tenant_id` injected via a Python closure at agent creation time. The LLM only knows about the function signature — it cannot accidentally leak one tenant's data into another's query. This is the safest pattern for multi-tenant tool use.

**Why three separate agent classes instead of one agent with a channel flag?**
Each channel needs genuinely different behavior: Voice responses must be short and contain no markdown (Polly reads asterisks out loud). Email responses need a professional greeting and sign-off. Chat can be flexible. Separate classes with separate system prompts makes each easy to tune independently without if/else in the LLM prompt.

**Why a rules-first EscalationEngine instead of asking the LLM?**
Rules are fast, deterministic, and auditable. If a customer types "fire", the escalation fires in microseconds without an LLM call. An LLM-based escalation check would add latency to every single turn and could produce inconsistent results. The LLM still has an `escalate_to_human` tool for cases the rules miss — the two work in parallel.

**Why n8n for automation instead of writing Slack/Zendesk code directly?**
n8n lets non-engineers modify what happens on escalation (change the Slack channel, add a new CRM step) without touching Python code. The agent only needs to fire one webhook — all downstream logic lives in the n8n canvas.

**Why sentence-transformers for embeddings instead of Groq/Google?**
Embeddings only need to run at ingestion time and at query time. A local model like `all-MiniLM-L6-v2` runs in milliseconds on CPU, costs nothing, and never sends document content to an external API. For a platform handling industrial manuals or sensitive operations data, this is the right default.

**Why SQLite for session storage?**
Zero infrastructure for development. The SQLAlchemy layer means swapping to Postgres in production is changing one `DATABASE_URL` environment variable — the async queries are identical.

**Why the email poller is disabled by default?**
`enable_email_poller=false` in the default config. Polling an SMTP inbox every 60 seconds requires IMAP credentials and can cause unexpected side effects in development (replying to real emails). It is opt-in via the `.env` flag once you have configured a dedicated support inbox.

---

## What Would Come Next in Production

| Current (Demo) | Production |
|---|---|
| Groq free tier | Groq paid or Azure OpenAI with SLA |
| ChromaDB on local disk | Pinecone / Weaviate / pgvector — survives restarts, scales horizontally |
| SQLite | PostgreSQL — concurrent writes, multi-instance safe |
| sentence-transformers local | Same model on GPU or swap to text-embedding-3-small (OpenAI) |
| n8n at localhost | n8n Cloud or self-hosted with persistent storage |
| HTTP polling for session history | Server-Sent Events for real-time agent streaming |
| No auth on chat endpoint | JWT tokens — customer login, session ownership |
| Single Uvicorn process | Gunicorn + multiple Uvicorn workers behind nginx |
| Email poller (IMAP polling) | Sendgrid Inbound Parse webhook — real-time, no polling |
| LangSmith not connected | LangSmith tracing — see every tool call, latency, and token count |
| Basic sentiment scoring | Proper NLP sentiment model (e.g., cardiffnlp/twitter-roberta) |

---

## Project File Map

```
Anti-support-agent/
│
├── app/
│   ├── main.py                  ← FastAPI app factory, lifespan events, route wiring
│   ├── config.py                ← All settings (loaded from .env via Pydantic Settings)
│   ├── dependencies.py          ← FastAPI dependency injection (DB session, auth)
│   │
│   ├── api/
│   │   ├── chat.py              ← WebSocket + HTTP chat endpoints, email endpoint
│   │   ├── admin.py             ← Tenant CRUD, knowledge ingestion, CSV extraction
│   │   ├── voice.py             ← Twilio TwiML voice webhooks
│   │   ├── n8n_webhooks.py      ← n8n calls back into the agent here
│   │   ├── demo.py              ← Demo surface endpoints
│   │   └── health.py            ← GET /health
│   │
│   ├── agents/
│   │   ├── base_agent.py        ← BaseAgent: LangChain LCEL chain builder
│   │   ├── support_agent.py     ← SupportAgent, VoiceAgent, EmailAgent + factory
│   │   ├── escalation_engine.py ← EscalationEngine (rules-first escalation logic)
│   │   ├── llm.py               ← LLM factory (Groq or Google)
│   │   └── prompts/
│   │       ├── system_prompt.py ← Chat system prompt template
│   │       ├── voice_prompt.py  ← Voice-optimized prompt
│   │       └── email_prompt.py  ← Email-optimized prompt
│   │
│   ├── channels/
│   │   ├── router.py            ← ChannelRouter: maps channel → agent
│   │   ├── chat.py              ← Chat channel handler
│   │   ├── voice.py             ← Twilio voice channel handler
│   │   └── email_handler.py     ← SMTP email send/poll
│   │
│   ├── rag/
│   │   ├── ingestion.py         ← ingest_documents() — full RAG ingestion pipeline
│   │   ├── loaders.py           ← load_documents() — PDF, URL, text loaders
│   │   ├── vectorstore.py       ← ChromaDB client + per-tenant collection getter
│   │   ├── embeddings.py        ← Embedding model wrapper
│   │   ├── retriever.py         ← LangChain retriever for the agent's search tool
│   │   └── csv_extractor.py     ← Regex/LLM alarm extraction from PDFs
│   │
│   ├── tools/
│   │   ├── knowledge_base.py    ← make_search_tool(tenant_id) — tenant-bound tool
│   │   └── escalation_tools.py  ← escalate_to_human @tool + _perform_escalation()
│   │
│   ├── services/
│   │   ├── session_service.py   ← Session + message CRUD (get_or_create, add_message)
│   │   └── tenant_service.py    ← Tenant CRUD + config resolution
│   │
│   ├── models/
│   │   ├── base.py              ← SQLAlchemy base + init_db()
│   │   ├── tenant.py            ← Tenant ORM model
│   │   ├── session.py           ← Session ORM model
│   │   ├── message.py           ← Message ORM model
│   │   ├── schemas.py           ← Pydantic request/response schemas
│   │   └── agent_models.py      ← Internal agent data models
│   │
│   ├── integrations/
│   │   └── n8n_client.py        ← n8n webhook client (notify_escalation, notify_new_session)
│   │
│   └── core/
│       ├── logging.py           ← structlog setup
│       ├── security.py          ← JWT token verification
│       ├── guardrails.py        ← Content safety rules
│       └── exceptions.py        ← Custom exception classes
│
├── demo.html                    ← Browser chat UI (served at /)
├── .env                         ← Local secrets (not committed)
├── .env.example                 ← Template for .env
├── pyproject.toml               ← Dependencies and project metadata
└── README.md                    ← The other app's README (IntelliDoc insurance tool)
```

---

*Built with LangChain · FastAPI · ChromaDB · Groq · sentence-transformers · n8n · Twilio*
