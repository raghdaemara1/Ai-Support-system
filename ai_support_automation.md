# AI Support System: Automation & Channel Architecture

This document explains the step-by-step functionality, automation mechanics, prompts, and tooling used in the Voice, Chat, and Email channels of the AI Support System.

---

## 1. Voice Channel

The Voice channel allows users to call a phone number and interact with the AI via a spoken conversation. 

### How it Works (Step-by-Step)
1. **Inbound Call:** A user dials the provisioned support number.
2. **Twilio Webhook:** Twilio receives the call and sends an HTTP POST request to the application's `/voice/incoming` endpoint (`app/channels/voice.py`).
3. **Greeting & Listening:** The app responds with an XML structure called **TwiML**. It uses the `<Say>` verb to verbally greet the user using Amazon Polly Text-to-Speech (TTS), and the `<Gather>` verb to activate Speech-to-Text (STT) and listen to the user.
4. **Transcription:** Once the user stops speaking, Twilio transcribes the audio into text and POSTs it to the `/voice/transcribed` endpoint.
5. **AI Processing:** The text is passed to the `SupportAgent` (`app/agents/support_agent.py`), which uses the RAG pipeline to search the ChromaDB knowledge base for relevant history or alarm codes.
6. **Execution & Response Generation:** The LLM generates a response based on the search context, user message, and voice-specific rules.
7. **Verbal Reply:** The backend cleans and sanitizes the response text (removing complex formatting like XML tags that break the TTS engine) and wraps it in a new TwiML `<Say>` block, which Twilio physically reads back to the user over the phone line.

### Voice Automation Logic
- **Safety First:** If the system (`app/agents/escalation_engine.py`) detects danger, high frustration, or the LLM's confidence falls below the escalation threshold, it automatically interrupts the loop.
- **Escalation Trigger:** The voice TwiML path diverges: instead of saying "Is there anything else I can help you with?", it declares "I am now connecting you to a human engineer." It gracefully breaks the AI loop and can trigger a physical call-transfer via Twilio's `<Dial>` verb.

### Voice-Specific Prompts
The Voice prompt (`app/agents/prompts/voice_prompt.py`) strictly enforces conversational behavior because *listening* requires a completely different pacing than *reading*.
- **Rules:** 
  - Maximum 2-3 sentences at a time.
  - No lists, bullet points, or complex formatting.
  - Spell out important details (e.g., tracking numbers).
- **Why?** A human reading an email can easily skim a 4-paragraph list. A human holding a phone to their ear cannot retain or follow a 4-paragraph audio dictation. The prompt forces the LLM to speak in short, natural bursts.

---

## 2. Chat (WebSocket) Channel

The Chat channel is the primary medium, allowing real-time, asynchronous communication through the browser.

### How it Works (Step-by-Step)
1. **Connection Initiation:** A user opens the chat widget in the UI, which opens a direct HTTP WebSocket connection to `/chat/ws/{tenant_id}/{customer_id}` (`app/api/chat.py`).
2. **Session Persistence:** A session is created or retrieved from the SQLite database, preserving conversation history so the LLM has context of prior turns.
3. **Message Flow:** A user types a message. It is transmitted instantly via the WebSocket.
4. **Asynchronous Timeout Guarantee:** To ensure the user isn't left hanging if the cloud LLM hangs, the backend wraps the LLM invocation in an `asyncio.wait_for` constraint with a hard timeout (e.g., 45s).
5. **Evaluation:** The Agent executes the tools (e.g., querying the DB, calculating values, or searching the RAG store).
6. **Streaming & Delivery:** The response is formatted into JSON and transmitted back across the socket along with latency metrics and the detected "intent" of the user.

### Chat Automation Trigger (Action vs. Information)
Chat acts as the primary "Agentic" surface. 
- **Information Request:** If a user asks "How do I fix alarm 105?", the LLM simply reads the VectorDB and replies (Information).
- **Automated Action:** If a user types "Please create a ticket for alarm 105", the LLM recognizes the action. It dynamically executes a python **tool function** (`_perform_escalation` or `ToolExecutor.create_ticket`), generating a physical database record in the SQLite database, before confirming to the user that the action was taken.

### Chat-Specific Prompts
The Core Agent prompt (`app/agents/prompts/system_prompt.py`) controls the main logic, encouraging succinct, professional text outputs. It leverages Markdown to organize information (bolding, headers) since the web interface can render rich text seamlessly.

---

## 3. Email Channel

The Email channel handles entirely decoupled, long-form conversations.

### How it Works (Step-by-Step)
1. **Background Polling:** A background task (`_email_poll_loop` in `app/main.py`) continuously wakes up (e.g., every 60 seconds) to poll the configured email inbox via the IMAP protocol (`app/channels/email_handler.py`).
2. **Reading Unseen Mail:** It grabs the subject, sender, and text body of any new unread emails.
3. **Session Assembly:** The backend combines the Subject line and Body text, binds it to a unique Session ID associated with the sender's email address, and invokes the `SupportAgent`.
4. **Drafting a Reply:** The LLM generates a localized, context-aware reply based on the email content.
5. **SMTP Dispatch:** The application logs into the Gmail SMTP server and physically sends a correctly formatted MIME email back to the customer.

### Email-Specific Prompts
The Email prompt (`app/agents/prompts/email_prompt.py`) mandates formal structure.
- **Rules:** Ensure proper formatting, numbered step-by-step instructions, clear paragraphs, and professional sign-offs. 
- **Why?** Since email has extreme latency (hours or days between replies), "conversational ping-pong" is frustrating. The LLM is commanded to be highly thorough and provide exhaustive solutions to bypass the need for endless back-and-forth emails.

---

## 4. Universal Automation Systems

Regardless of the channel, two core engines govern how decisions are made.

### The RAG Pipeline (Information Automation)
- We use **HuggingFace MiniLM** to convert the user's plain text English question into an array of mathematical numbers (Embeddings).
- We use **ChromaDB** to compare those numbers against all the technical manuals we fed the system. The database mathematically discovers the closest matching paragraphs.
- **Why we use this:** Without RAG (Retrieval-Augmented Generation), an LLM hallucinates or gives generic advice. With RAG, the LLM physically reads the exact page of the machine's manual *before* answering the user. It automates "looking up the documentation."

### The Escalation Engine (Routing Automation)
- `app/agents/escalation_engine.py` operates as a standalone safety governor.
- **Concept:** LLMs get confused. Humans get angry. We cannot trust the LLM to manage its own failures entirely.
- **Implementation:** The Escalation Engine intercepts the LLM's response *before* it is sent to the user. It uses **Regex matching** and rule-based checks:
  - Did the user type words like "fire", "danger", "human", "stuck"? -> **Escalate immediately.**
  - Did the LLM output phrases like "I don't know", "I'm not sure", or "Please contact support"? -> **Escalate immediately.**
- **Action:** When Escalation is triggered, it writes a payload to an escalation queue, generates a high-priority ticket, and immediately routes the context to a human dashboard, bypassing the AI entirely.
