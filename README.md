# AI Customer Support Agent - Free Tier

A production-grade, multi-channel AI customer support agent platform built entirely on **free tier** services.

## Features

- **Multi-channel support**: Chat (WebSocket), with architecture ready for voice and email
- **RAG-powered responses**: Knowledge base search using ChromaDB (local, free)
- **Smart escalation**: Automatic detection of when to hand off to humans
- **Multi-tenant**: Support multiple enterprise customers with isolated data
- **Free LLM options**: Groq (Llama 3.3) or Google Gemini free tiers

## Free Tier Stack

| Component | Technology | Notes |
|-----------|------------|-------|
| **LLM** | Groq or Google Gemini | Free API tiers |
| **Embeddings** | HuggingFace sentence-transformers | Local, free |
| **Vector Store** | ChromaDB | Local, free |
| **Database** | SQLite | Local, free |
| **Session Cache** | In-memory | Free |
| **Web Framework** | FastAPI | Free, open source |

## Quick Start

### 1. Prerequisites

- Python 3.11+
- A free API key from either:
  - [Groq](https://console.groq.com/) (recommended - fast inference)
  - [Google AI Studio](https://makersuite.google.com/app/apikey) (Gemini)

### 2. Installation

```bash
# Clone the repository
cd ai-support-agent

# Create virtual environment
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Configuration

```bash
# Copy environment template
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux

# Edit .env and add your API key
# For Groq:
GROQ_API_KEY=gsk_your_key_here
LLM_PROVIDER=groq

# OR for Google Gemini:
GOOGLE_API_KEY=your_key_here
LLM_PROVIDER=google
```

### 4. Run the Server

```bash
# Start the API server
uvicorn app.main:app --reload --port 8000
```

### 5. Access the API

- **API Docs**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Usage

### Create a Tenant

```bash
curl -X POST http://localhost:8000/admin/tenants \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Company",
    "slug": "my-company",
    "config": {
      "persona_name": "Aria",
      "persona_description": "A helpful customer support agent for My Company"
    }
  }'
```

**Save the API key returned - it won't be shown again!**

### Add Knowledge Base Content

```bash
# Add text content
curl -X POST "http://localhost:8000/admin/tenants/{tenant_id}/knowledge" \
  -H "Content-Type: application/json" \
  -d '{
    "sources": [
      {
        "type": "text",
        "content": "Our store hours are Monday-Friday 9am-5pm. We are closed on weekends.",
        "source_name": "store_info"
      },
      {
        "type": "text",
        "content": "Returns are accepted within 30 days with receipt. Refunds take 5-7 business days.",
        "source_name": "return_policy"
      }
    ]
  }'
```

### Chat with the Agent

**HTTP Endpoint:**
```bash
curl -X POST http://localhost:8000/chat/message \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_id": "your-tenant-id",
    "customer_id": "customer-123",
    "message": "What are your store hours?"
  }'
```

**WebSocket (for real-time chat):**
```javascript
const ws = new WebSocket('ws://localhost:8000/chat/ws/{tenant_id}/{customer_id}');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data.content);
};

ws.send(JSON.stringify({ message: "Hello!" }));
```

## Project Structure

```
ai-support-agent/
├── app/
│   ├── api/          # HTTP endpoints
│   ├── agents/       # LLM agent implementations
│   ├── tools/        # LangChain tools
│   ├── rag/          # Retrieval pipeline
│   ├── escalation/   # Human handoff logic
│   ├── models/       # Database models
│   ├── services/     # Business logic
│   └── core/         # Utilities
├── tests/
├── requirements.txt
└── docker-compose.yml
```

## Docker Deployment

```bash
# Build and run
docker-compose up --build

# The API will be available at http://localhost:8000
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/admin/tenants` | POST | Create tenant |
| `/admin/tenants` | GET | List tenants |
| `/admin/tenants/{id}/knowledge` | POST | Add knowledge |
| `/chat/message` | POST | Send chat message |
| `/chat/ws/{tenant}/{customer}` | WS | Real-time chat |

## Upgrading to Paid Tiers

When ready to scale, you can upgrade individual components:

| Free | Paid Alternative |
|------|------------------|
| Groq/Gemini | OpenAI GPT-4o, Anthropic Claude |
| ChromaDB | Pinecone, Weaviate |
| SQLite | PostgreSQL |
| In-memory | Redis |

The architecture is designed to make these swaps straightforward.

## License

MIT License
