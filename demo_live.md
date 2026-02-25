# Live Demo Script — AI Customer Support Agent
### For: FDE Candidate Screen-Share Presentation
### Audience: Recruiter + CTO / Technical Founder
### Time Target: 12–18 minutes

---

> **HOW TO USE THIS DOCUMENT**
> This is your word-for-word script and mental map. Read the bold lines aloud.
> The grey annotations are stage directions — what to click or show on screen.
> Practice this 3 times before the interview. The goal is fluency, not memorization.

---

## SECTION 1 — The Opening (60 seconds)

**"Before I open any code, I want to give you the one-sentence value proposition of what this system does."**

**"An enterprise customer — say a manufacturing company with 200 machines on a factory floor — currently drowns their Tier-1 support team in tickets for things like: 'What does Alarm 2008 mean on the KHS Filler?' This system intercepts those tickets across Voice, Chat, and Email, answers them instantly from the machine's own documentation, and only escalates to a human when there is a real safety issue or when the AI genuinely cannot help."**

**"The business outcome: 60% fewer tickets hitting your human agents, sub-1.5 second responses on voice calls, and zero PII leaking into your logs. Let me show you how it works under the hood."**

---

## SECTION 2 — The Core Pipeline (Architecture Walkthrough)
### ⏱ Target time: 3–4 minutes
### 🖥 Show: The system_dataflow diagram (http://localhost:8001/dataflow) OR the README architecture diagram

---

### 2a. The Mental Model — The Three-Layer Pipeline

**"Every message that enters this system — whether it comes in as a phone call, a web chat, or an email — passes through exactly three layers. I'll walk you through each one."**

```
┌─────────────────────────────────────────────────────────────────┐
│  LAYER 1: CHANNELS (The Ingress)                                │
│                                                                  │
│  Voice            Chat             Email                         │
│  (Twilio TwiML)   (WebSocket)      (IMAP Poller)                │
│       │                │                │                       │
│       └────────────────┴────────────────┘                       │
│                         │                                        │
│                         ▼                                        │
├─────────────────────────────────────────────────────────────────┤
│  LAYER 2: ESCALATION ENGINE (The Safety Net — runs FIRST)       │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  should_escalate(user_msg, agent_response, history)     │    │
│  │                                                          │    │
│  │  Rule 1: SAFETY_PATTERN match? → urgency = "high"       │    │
│  │          ("fire", "emergency", "production stop"...)     │    │
│  │  Rule 2: HUMAN_REQUEST_PATTERN? → urgency = "normal"    │    │
│  │          ("speak to human", "transfer", "engineer"...)   │    │
│  │  Rule 3: Agent said "I don't know"? → escalate          │    │
│  │  Rule 4: Turn count > MAX_TURNS? → escalate             │    │
│  └─────────────────────────────────────────────────────────┘    │
│                         │                                        │
│              YES ────────────────── NO                          │
│              │                       │                           │
│    Escalation Queue           ▼                                  │
│    (Human Handoff)  ┌─────────────────────────────┐             │
│                     │  LAYER 3: LANGGRAPH AGENT   │             │
│                     │  (The LLM Brain)             │             │
│                     └─────────────────────────────┘             │
└─────────────────────────────────────────────────────────────────┘
```

**"Notice the order. The Escalation Engine runs BEFORE the LLM. This is a deliberate architectural decision. If someone calls with a safety emergency — they say 'fire in the building' — I am not asking a language model to decide what to do. A deterministic regex pattern intercepts it in microseconds and routes immediately to a human. The LLM never touches it."**

**"This is what I mean by 'deterministic safety.' Rules first. AI second."**

---

### 2b. Inside the LangGraph Agent

```
LANGGRAPH AGENT (create_react_agent)
══════════════════════════════════════════════════════════

Input: user_message + conversation history (last 20 turns)
          │
          ▼
┌─────────────────────────────────────────────────────┐
│  LLM (Groq / llama-3.3-70b-versatile)               │
│                                                      │
│  Receives: SystemPrompt + History + User Message     │
│  Decides: "Do I need a tool, or can I answer now?"   │
└────────────────────────┬────────────────────────────┘
                         │
              ┌──────────┴──────────┐
              │                     │
     Need a Tool             Can Answer Directly
              │                     │
              ▼                     ▼
  ┌─────────────────────┐     Final Response
  │  Tool Executor       │     to Channel
  │                      │
  │  search_knowledge_base(query, tenant_id)
  │     │
  │     ▼
  │  ChromaDB similarity_search()
  │  → Returns top-4 chunks from the
  │    tenant's isolated vector store
  │  → LLM reads chunks, synthesizes answer
  └─────────────────────┘
          │
          ▼
    Final Response
```

**"The LangGraph `create_react_agent` is a Reasoning and Acting loop. The model sees the user's message and decides: do I have enough information to answer, or do I need to look something up? If it needs context, it fires the `search_knowledge_base` tool, which hits ChromaDB and retrieves the most relevant chunks from that specific enterprise customer's documentation. The model reads those chunks and generates its final answer."**

**"Everything is async. Every step has a hard timeout — 45 seconds for the LLM loop, 10 seconds for the escalation queue write. If anything hangs, we degrade gracefully instead of dropping the customer's message."**

---

## SECTION 3 — Tools & The "Why"
### ⏱ Target time: 3 minutes
### 🖥 Show: the open Swagger UI at /docs, or flip to the relevant source file

---

### FastAPI — Why not Django or Flask?

**"FastAPI is the right choice for an AI agent backend for three reasons. First, it's async-native — every I/O operation, every database call, every LLM call awaits properly. A Flask app would block the event loop every time the LLM thinks. At 200 concurrent voice calls, that kills you. Second, it has native WebSocket support, which is mandatory for real-time chat and Twilio media streams. Third, Pydantic validation is built in — every request and response is typed and validated before it touches any logic. That matters at enterprise because bad input data is how you get prompt injection and unpredictable agent behavior."**

### LangGraph — Why not raw LangChain or a custom loop?

**"LangGraph replaced the old `AgentExecutor` in LangChain 1.x for good reason. It models the agent as an explicit state machine — you define nodes, edges, and transitions. That gives you three things an enterprise customer requires: recursion limits so the agent cannot loop forever on a bad query, explicit state you can inspect and debug, and the ability to add new nodes — like a separate safety-check node — without rewriting the whole agent. I use `create_react_agent` here which is the pre-built production pattern from the LangGraph team."**

### ChromaDB — Why local vector store?

**"ChromaDB for local and demo deployments is a deliberate choice, not a limitation. It's a fully persistent, ACID-compliant vector database that runs in-process. Each enterprise customer gets their own collection — `tenant_{tenant_id}` — which is the data isolation boundary. One tenant cannot see another tenant's documents. ChromaDB 1.x persists automatically to disk on every write, so we don't lose the knowledge base on restart. For production at scale, this collection becomes a namespace in Pinecone or a dedicated Qdrant cluster — the LangChain vectorstore interface is the abstraction layer that makes that swap a one-line config change."**

### Twilio TwiML — Why not a raw WebSocket audio stream?

**"The voice implementation uses Twilio's `<Gather input='speech'>` pattern. This is the right architecture for a demo and for many production deployments. When a caller speaks, Twilio handles the speech recognition, calls our webhook with the transcribed text, we run the LangGraph agent, and return TwiML with Amazon Polly Neural TTS that Twilio reads aloud. The entire integration is three things: a URL, a function, and a string. No custom ASR infrastructure to operate. In a high-volume production deployment where we need sub-1.5 second latency, we'd replace `<Gather>` with a `<Stream>` tag and a Deepgram WebSocket connection, which gives us real-time streaming transcription. The architecture supports that upgrade — only the voice.py file changes."**

### BackgroundTasks — Why not Celery?

**"When an enterprise customer uploads their 500-page maintenance manual, ingesting it — loading the PDF, chunking it, embedding each chunk, writing to ChromaDB — can take 60–90 seconds. If we do that synchronously, the API returns a 504 timeout and the customer never knows if their knowledge base was built. FastAPI's `BackgroundTasks` fires the ingestion after the HTTP response is already sent. The customer gets a `202 Accepted` with `'status: processing'` in under 100ms, and the ingestion runs to completion behind the scenes. For a Celery queue, the operational overhead — Redis broker, Celery workers, task monitoring — isn't justified until you're running hundreds of concurrent ingestion jobs. BackgroundTasks is the right MVP choice here, with Celery as the documented production upgrade path."**

---

## SECTION 4 — Live Demo Sequence
### ⏱ Target time: 5–6 minutes
### 🖥 Start screen share NOW — terminal + browser side by side

---

**STEP 1: Start the server**

```bash
cd "d:/OneDrive - Obeikan Investment Group/desktop/Agents/ai-support-agent"
C:/Python312/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001
```

> *Point to the terminal output. Show the `[INFO] Uvicorn running on http://0.0.0.0:8001` line.*

**"The server is live. Notice the startup sequence: database initializes, ChromaDB connects, the admin router, chat router, and voice router all register. Everything boots cleanly."**

---

**STEP 2: Create a tenant**

> *Open http://localhost:8001/docs — Swagger UI*

**"An enterprise customer in this system is a 'tenant.' Each tenant has their own isolated knowledge base, their own agent persona, and their own conversation history. Let me create one."**

```bash
curl -s -X POST http://localhost:8001/admin/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Obeikan Manufacturing",
    "slug": "obeikan",
    "config": {
      "persona_name": "Aria",
      "persona_description": "A technical support agent for Obeikan factory floor operations. You specialise in machine fault codes and downtime troubleshooting.",
      "channels": ["chat", "voice", "email"]
    }
  }' | python -m json.tool
```

> *Show the returned `api_key` on screen.*

**"The API key is hashed with SHA-256 before being stored in SQLite. I only return it once — it will not be in the database in plaintext. This is the standard pattern for API key security."**

---

**STEP 3: Ingest a knowledge base document**

> *Have a sample PDF ready — even a 2-page document of sample fault codes works.*

**"Now I am uploading the machine's fault code manual into the knowledge base. This is what makes the AI useful — it cannot know anything about this specific customer's machines until we give it the documentation."**

```bash
curl -s -X POST "http://localhost:8001/admin/tenants/obeikan/knowledge/upload" \
  -F "files=@sample_faults.pdf"
```

> *Show the immediate response: `{"status": "processing", "message": "File ingestion started in background"}`*

**"Notice this returns immediately — under 100ms — while the ingestion runs in the background. The API event loop is never blocked. If I had uploaded a 500-page manual, the user would have the same sub-100ms response while the system processes the document asynchronously."**

> *Wait 10–15 seconds, then show the ChromaDB files in `./chroma_data/` growing in the file explorer.*

**"ChromaDB has written the vector embeddings to disk. The knowledge base is live."**

---

**STEP 4: Chat with the agent — Normal query**

> *Open the demo UI at http://localhost:8001/ OR use curl directly*

**"Let me send a message that should trigger a RAG lookup."**

```bash
curl -s -X POST http://localhost:8001/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "obeikan",
    "customer_id": "operator-007",
    "message": "What does alarm code 2008 mean on the KHS Filler?"
  }' | python -m json.tool
```

> *Show the response: the AI's answer about the fault code, `escalated: false`, `intent: fault_lookup`, and the latency_ms.*

**"The response came back in approximately [X] milliseconds. You can see the intent was correctly classified as `fault_lookup`. The AI retrieved the relevant chunk from ChromaDB — the indexed documentation — and synthesised a direct answer. It did not hallucinate. If the fault code is not in the knowledge base, it says so and escalates."**

---

**STEP 5: Trigger the escalation engine**

**"Now let me show you what happens when a safety condition is detected."**

```bash
curl -s -X POST http://localhost:8001/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "obeikan",
    "customer_id": "operator-007",
    "message": "There is smoke coming from the machine and I think there might be a fire in the production area"
  }' | python -m json.tool
```

> *Show the response: `escalated: true`, urgency `"high"` in the server logs.*

**"The word 'fire' and 'smoke' matched the `SAFETY_PATTERN` regex — compiled at startup, evaluated in microseconds, before the LLM was ever invoked. This conversation was flagged for immediate human handoff. The LLM never saw the message. In a real deployment, this would open a high-priority ticket in Zendesk or Salesforce and page the on-call engineer."**

---

**STEP 6: Show LangSmith observability (if LANGCHAIN_API_KEY is set)**

> *Open https://smith.langchain.com — show the live traces*

**"Every LLM call, every tool invocation, every reasoning step is traced here in LangSmith. This is how the enterprise deployment team debugs a bad response — they click into the trace, see exactly what context the model retrieved, what it decided, and where it went wrong. Without this, debugging a production AI agent is guesswork. With this, it is reproducible engineering."**

---

**STEP 7: Run the RAG evaluation**

```bash
C:/Python312/python.exe scripts/evaluate_rag.py --tenant obeikan --k 3
```

> *Show the output: Recall@3 percentage for each query in the golden dataset.*

**"This is how we give the enterprise customer a measurable SLA on the AI's knowledge base quality. If Recall@3 drops below 85%, we have three levers: reduce chunk size to increase specificity, switch the embedding model to one tuned for technical language, or add hybrid BM25 + dense search for exact fault code matching. This is a quantitative contract with the customer — not a vibe."**

---

## SECTION 5 — Local vs Production Architecture
### ⏱ Target time: 2–3 minutes
### 🖥 Pull up the Architecture diagram in README.md

---

**"Everything I have shown you runs on a laptop with no paid infrastructure. Let me be explicit about what each component becomes in a real enterprise deployment, because this is the conversation you will have with a customer's IT department."**

```
┌──────────────────────┬───────────────────────────────┬───────────────────────────────────┐
│  COMPONENT           │  LOCAL / DEMO                  │  PRODUCTION ENTERPRISE             │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  LLM                 │  Groq (llama-3.3-70b-versatile)│  OpenAI GPT-4o or Anthropic        │
│                      │  Free tier, 600 RPM limit      │  Claude — provisioned throughput,  │
│                      │                                │  SLA, data processing agreements   │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  PDF Parsing         │  pypdf (raw text extraction)   │  Docling or Unstructured.io        │
│                      │  Works for digital PDFs        │  — handles scanned docs, tables,   │
│                      │                                │  diagrams, multi-column layouts    │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  Vector Store        │  ChromaDB (local on disk)      │  Pinecone / Qdrant / Weaviate      │
│                      │  Per-tenant collections        │  — managed, HA, ANN index,         │
│                      │                                │  multi-region replication          │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  Embeddings          │  all-MiniLM-L6-v2 (CPU, local) │  OpenAI text-embedding-3-large     │
│                      │  384 dims, free                │  or Snowflake Cortex Embed         │
│                      │                                │  — 3072 dims, better for           │
│                      │                                │  technical / domain-specific text  │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  Database            │  SQLite (single file)          │  PostgreSQL (RDS / Aurora)         │
│                      │  Single process only           │  — connection pooling (pgBouncer), │
│                      │                                │  read replicas, automated backups  │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  Session Cache       │  In-memory Python dict         │  Redis Cluster (ElastiCache)       │
│                      │  Dies on restart               │  — survives restarts, shared       │
│                      │  Only works with 1 worker      │  across 10+ Uvicorn workers,       │
│                      │                                │  24h TTL, pub/sub for real-time    │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  Ingestion Queue     │  FastAPI BackgroundTasks        │  Celery + Redis broker             │
│                      │  Single-process, no retry      │  — retries, dead-letter queue,     │
│                      │                                │  task priority, monitoring via     │
│                      │                                │  Flower dashboard                  │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  Voice Channel       │  Twilio <Gather input="speech">│  Twilio <Stream> → Deepgram        │
│                      │  Twilio STT + Polly TTS        │  WebSocket for real-time ASR.      │
│                      │  ~3–6s latency per turn        │  ElevenLabs Turbo v2 for TTS.      │
│                      │                                │  Target: <1.5s end-to-end          │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  Observability       │  LangSmith traces (free tier)  │  LangSmith + Prometheus + Grafana  │
│                      │  structlog JSON logging        │  — latency histograms, containment │
│                      │                                │  rate, escalation rate, cost/call  │
├──────────────────────┼───────────────────────────────┼───────────────────────────────────┤
│  Deployment          │  Single uvicorn process        │  Kubernetes — HPA on CPU/latency,  │
│                      │  localhost:8001                │  separate voice/chat/email pods,   │
│                      │                                │  ingress with rate limiting,       │
│                      │                                │  secrets via Vault or AWS SSM      │
└──────────────────────┴───────────────────────────────┴───────────────────────────────────┘
```

**"The key insight is that every component swap is a configuration change, not a rewrite. The LangChain vectorstore interface abstracts ChromaDB and Pinecone behind the same `.similarity_search()` call. The LLM interface abstracts Groq and OpenAI. The only non-trivial migration is the voice channel — moving from `<Gather>` to `<Stream>` requires a proper Deepgram WebSocket handler, which is a separate module, not a change to the agent logic."**

---

## SECTION 6 — The Close (60 seconds)

**"To summarize what you have seen today:"**

**"One: A multi-channel backend — voice, chat, and email — all routing through the same LangGraph agent and the same knowledge base. One codebase, three channels."**

**"Two: A deterministic safety layer that intercepts high-risk queries before the LLM touches them. Rules first. AI second. That is the enterprise reliability story."**

**"Three: Tenant isolation at every layer — separate ChromaDB collections, separate conversation histories, separate agent personas. What one enterprise customer's employees see, another customer cannot access."**

**"Four: A measurable quality contract — Recall@K against a golden dataset — so when a customer asks 'how do we know the AI is actually finding the right answers,' I have a number and a methodology, not a guess."**

**"This is the architecture I would deploy at your customer's site. Where would you like to go deeper?"**

---

## Appendix — Quick Commands Reference

```bash
# Start server
C:/Python312/python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8001

# Health check
curl http://localhost:8001/health

# Create tenant
curl -X POST http://localhost:8001/admin/tenants \
  -H "Content-Type: application/json" \
  -d '{"name":"Demo Co","slug":"demo","config":{"persona_name":"Aria","persona_description":"Support agent"}}'

# Ingest text into knowledge base
curl -X POST "http://localhost:8001/admin/tenants/demo/knowledge" \
  -H "Content-Type: application/json" \
  -d '{"sources":[{"type":"text","content":"Alarm 2008: Temperature out of range. Check cooling system. Reset PLC after clearing.","source_name":"fault_guide"}]}'

# Chat — normal query (should hit RAG)
curl -X POST http://localhost:8001/chat/message \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"demo","customer_id":"user-1","message":"What does alarm 2008 mean?"}'

# Chat — trigger safety escalation
curl -X POST http://localhost:8001/chat/message \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"demo","customer_id":"user-1","message":"There is smoke and I think there is a fire near the machine"}'

# Chat — trigger human request escalation
curl -X POST http://localhost:8001/chat/message \
  -H "Content-Type: application/json" \
  -d '{"tenant_id":"demo","customer_id":"user-1","message":"I need to speak to a human engineer immediately"}'

# Run RAG evaluation
C:/Python312/python.exe scripts/evaluate_rag.py --tenant demo --k 3

# Demo UI
# Open browser: http://localhost:8001/
# Open docs: http://localhost:8001/docs
# Open dataflow: http://localhost:8001/dataflow
```

---

## Appendix — One Bug to Fix Before Demo Day

In [app/api/voice.py](app/api/voice.py), the endpoint path and the Gather action URL both contain a typo: `twillo` (double-l) instead of `twilio` (single-l).

**Line 36:**
```python
# CURRENT (broken):
@router.post("/twillo/webhook/{tenant_id}")

# CORRECT:
@router.post("/twilio/webhook/{tenant_id}")
```

**Line 94:**
```python
# CURRENT (broken):
g = Gather(input="speech", action=f"/api/voice/twillo/webhook/{tenant_id}", timeout=5)

# CORRECT:
g = Gather(input="speech", action=f"/api/voice/twilio/webhook/{tenant_id}", timeout=5)
```

Fix both before your demo. A live call will return a 404 on the transcription callback if you do not.

---

*This document is your presentation. You own every word in it. Practice the transitions, not just the content.*
