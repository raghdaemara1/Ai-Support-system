# Interview File 1: LangGraph Foundations (From Zero)

This file teaches LangGraph from scratch, then maps those concepts to your current app.

---

## What Is LangGraph?

LangGraph is a framework for building **stateful, multi-step LLM workflows** as a graph.

Instead of one linear pipeline, you define:
- **State**: shared memory object
- **Nodes**: functions that read/write state
- **Edges**: routing rules from one node to the next

So execution is:
`node -> node -> node`, not just `prompt -> response`.

---

## Why It Exists

Classic chains are good for simple flows.
Real support systems need:
- loops
- tool retries
- branching
- memory
- escalation paths

LangGraph gives those control patterns directly.

---

## Core Concepts

## 1) State

State is the shared data object every node can read/write.

Example:

```python
from typing import TypedDict, Optional

class GraphState(TypedDict):
    user_message: str
    intent: str
    kb_results: list[str]
    answer: str
    escalated: bool
```

Each node returns partial updates like:

```python
return {"intent": "fault_lookup"}
```

LangGraph merges updates into the global state.

## 2) Nodes

Node = Python function.
It receives state and returns state updates.

Example:

```python
def classify_intent(state: GraphState):
    text = state["user_message"].lower()
    if "alarm" in text or "error" in text:
        return {"intent": "fault_lookup"}
    return {"intent": "general"}
```

## 3) Edges

Edges define flow:
- fixed edge (`A -> B`)
- conditional edge (`if intent == fault_lookup -> search_kb else -> answer`)

---

## Mental Model

Without graph:

`User -> LLM -> Tool -> LLM -> Output`

With graph:

1. Read message
2. Decide route
3. Maybe call tool
4. Maybe escalate
5. Format response
6. End

That is exactly what enterprise support needs.

---

## Minimal Example (Your Requested Structure)

## Step 1: Define State

```python
from typing import TypedDict

class GraphState(TypedDict):
    question: str
    answer: str
```

## Step 2: Create Node

```python
from langchain.chat_models import ChatOpenAI

llm = ChatOpenAI(model="gpt-4o-mini")

def generate_answer(state: GraphState):
    response = llm.invoke(state["question"])
    return {"answer": response.content}
```

## Step 3: Build Graph

```python
from langgraph.graph import StateGraph, END

builder = StateGraph(GraphState)
builder.add_node("generate", generate_answer)
builder.set_entry_point("generate")
builder.add_edge("generate", END)

graph = builder.compile()
```

## Step 4: Run

```python
result = graph.invoke({"question": "What is LangGraph?"})
print(result["answer"])
```

---

## Real Agent Pattern (Support Use Case)

Typical support graph:
1. `ingest_message`
2. `classify_intent`
3. `retrieve_kb`
4. `generate_answer`
5. `check_escalation`
6. `handoff_or_finish`

This gives:
- deterministic control
- observable decision points
- safe escalation

---

## How LangGraph Appears In Your Repo

LangGraph is used in the `app/agents` stack.

Key file:
- [app/agents/base_agent.py](d:\OneDrive - Obeikan Investment Group\desktop\Agents\ai-support-agent\app\agents\base_agent.py)

Important lines conceptually:
1. `create_react_agent(...)` builds graph runtime
2. `ainvoke({"messages": ...}, config={"recursion_limit": 4})` executes graph
3. Tools are attached from:
   - KB search tool
   - escalation tool

So your app already uses graph-style execution for tool orchestration.

---

## Why Recursion Limit Matters

In agent/tool loops, LLM might repeatedly call tools.
`recursion_limit=4` prevents infinite loops.

Interview wording:
"We cap graph recursion to enforce bounded execution and predictable latency."

---

## LangGraph vs Your Demo Stack

You also have `app/agent/*` (spec/demo path) which is simpler and not full LangGraph orchestration.

Interview wording:
"I keep a full LangGraph production-style path and a lightweight spec demo path for rapid channel demos."

---

## Final 30-Second Answer

"LangGraph is a stateful orchestration runtime for LLM workflows. I model support handling as nodes over shared state, with conditional edges for retrieval, escalation, and handoff. In my app, LangGraph powers the multi-tenant chat/email stack with tool-calling and bounded loops, while a lightweight demo path exists for quick voice/chat demonstrations."

