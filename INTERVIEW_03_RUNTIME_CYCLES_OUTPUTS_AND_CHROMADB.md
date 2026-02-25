# Interview File 3: Runtime Cycles, Payloads, and ChromaDB Internals

This file explains what happens at runtime, how automation cycles behave, and what data structures look like.

---

## 1. Runtime Cycles (All Loops In The System)

## Cycle A: FastAPI lifespan loop
File: `app/main.py`

Lifecycle:
1. startup
2. init DB
3. optionally launch email poll task
4. serve requests continuously
5. cancel tasks on shutdown

## Cycle B: Email poll loop
File: `app/main.py` `_email_poll_loop()`

Pattern:
1. call `poll_inbox_async()`
2. sleep interval
3. repeat forever

## Cycle C: WebSocket chat loop (LangGraph)
File: `app/api/chat.py` `chat_websocket(...)`

Pattern:
1. receive frame
2. process via agent
3. emit response frame
4. emit done frame
5. repeat

## Cycle D: WebSocket chat loop (Spec)
File: `app/channels/chat.py` `chat_websocket_handler(...)`

Pattern:
1. receive message
2. run `SupportAgent.respond(...)`
3. send result
4. if escalated -> send handoff frame + break

## Cycle E: Voice interaction loop (Webhook callback loop)
File: `app/channels/voice.py`

Pattern across HTTP requests:
1. Twilio asks for prompt (`/incoming`)
2. user speaks
3. Twilio posts transcript (`/transcribed`)
4. app returns next `<Gather>` to continue
5. repeats until caller hangs up or escalation flow

---

## 2. Retries / Timeouts / Guardrails

LangGraph HTTP and WS routes apply timeout:
- `asyncio.wait_for(..., timeout=LLM_TIMEOUT)`

Escalation queue writes also guarded by timeout:
- `wait_for(_perform_escalation(...), timeout=10.0)`

Graph safety:
- recursion limit `4` in `BaseAgent`

Practical result:
- requests fail fast
- no infinite tool loops
- controlled latency envelope

---

## 3. State Objects You Should Know

## LangGraph route response model
From `/chat/message`:

```json
{
  "session_id": "uuid",
  "message": "assistant text",
  "escalated": false,
  "intent": "fault_lookup",
  "sources": []
}
```

## Spec route response model
From `/api/chat`:

```json
{
  "message": "assistant text",
  "intent": "fault_lookup",
  "confidence": 0.89,
  "escalated": false,
  "sources": ["source snippet"],
  "ticket": null
}
```

## Ticket shape (spec stack)
From `app/models/agent_models.py`:

```json
{
  "ticket_id": "TKT-AB12CD34",
  "session_id": "demo-1",
  "channel": "chat",
  "summary": "Emergency: smoke in line 2",
  "machine": "KHS_Filler",
  "alarm_code": "282",
  "priority": "medium",
  "status": "open",
  "created_at": "2026-02-25T10:00:00Z"
}
```

---

## 4. ChromaDB: What Is Stored

Each record typically stores:
1. `id`
2. `embedding` vector (float array)
3. `document` text
4. `metadata` dict

Example metadata:

```json
{
  "alarm_id": "282",
  "description": "Hydraulic pressure low",
  "cause": "Pump wear",
  "action": "Inspect pump and replace seal",
  "machine": "KHS_Filler",
  "reason_1": "pressure"
}
```

---

## 5. ChromaDB Query Output Shape (Raw)

When calling `collection.query(...)`, result is shaped like:

```json
{
  "ids": [["KHS_Filler_282", "KHS_Filler_9093"]],
  "documents": [[
    "Alarm 282: Hydraulic pressure low. Cause: Pump wear. Action: Inspect pump and replace seal.",
    "Alarm 9093: Motor overload. Cause: Bearing friction. Action: Stop line and inspect bearing."
  ]],
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

Your code converts that to `KBSearchResult`:
- score = `1 - distance`
- first result above => `0.89`

---

## 6. End-to-End Example: Chat Request (Spec Stack)

Input:

```json
{
  "message": "Alarm 282 on KHS filler",
  "session_id": "demo-a1",
  "machine": "KHS_Filler"
}
```

Execution:
1. session loaded
2. message appended to history
3. RAG query gets top 3
4. LLM/fallback composes answer
5. confidence computed
6. escalation check
7. ticket maybe created
8. JSON returned

Output example:

```json
{
  "message": "What this alarm means: Alarm 282 indicates hydraulic pressure deviation.\nLikely cause: Pump wear.\nWhat to do: 1) Inspect pump. 2) Replace seal. 3) Validate pressure reset.",
  "intent": "fault_lookup",
  "confidence": 0.89,
  "escalated": false,
  "sources": ["Hydraulic pressure low on filler module"],
  "ticket": null
}
```

---

## 7. End-to-End Example: Voice Request

Call enters `/api/voice/incoming`:
- TwiML asks user to speak.

Twilio posts transcription to `/api/voice/transcribed` with:
- `SpeechResult`
- `CallSid`

App response TwiML (normal):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna">Here is what the alarm means...</Say>
  <Gather input="speech" action="/api/voice/transcribed" speechTimeout="auto">
    <Say voice="Polly.Joanna">Is there anything else I can help you with?</Say>
  </Gather>
</Response>
```

Escalation variant:
- includes handoff message and does not continue gather loop.

---

## 8. End-to-End Example: Email Automation

Polling cycle:
1. IMAP unseen fetch
2. parse message
3. run support agent
4. SMTP reply
5. mark seen

Input email:
- Subject: `Fault 282 - line stopped`
- Body: `KHS filler has alarm 282`

Output email body:
- concise cause + action
- escalation suggestion if needed

---

## 9. Failure Paths You Should Be Ready To Explain

1. No KB results:
- confidence drops
- response says no record found
- escalation may trigger

2. LLM timeout:
- HTTP 504 on guarded endpoints

3. SMTP/IMAP missing creds:
- email poller exits safely (no crash)

4. Tool-call malformed output (LangGraph stack):
- response cleanup logic strips tool artifacts

---

## 10. Interview Answers For "What Happens Underneath?"

Use this:

"Underneath, each request becomes a state transition pipeline.  
Session state is loaded, retrieval augments context from ChromaDB, agent inference runs with bounded recursion and tool access, escalation rules evaluate deterministic safety conditions, then channel-specific rendering returns JSON/TwiML/SMTP output.  
In parallel, background loops handle polling and long-lived websocket interactions."

---

## 11. How To Study These 3 Files

1. Read file 1 first: LangGraph mental model.
2. Read file 2 second: exact classes/method call order.
3. Read file 3 third: runtime loops and payload examples.

If you can explain all three in your own words, you are interview-ready.

