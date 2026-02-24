import uuid

import httpx
import streamlit as st

st.set_page_config(page_title="AI Support Agent Demo", page_icon=":robot_face:", layout="wide")
st.title("Multi-Channel AI Support Agent")
st.caption("Industrial equipment support - chat, voice, and email")

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())
if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.header("Demo Controls")
    machine = st.text_input("Machine Context", value="KHS_Filler")
    st.divider()
    st.subheader("Try these")
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
                for source in msg["sources"]:
                    st.caption(f"- {source}")

if prompt := st.chat_input("Describe the issue or enter an alarm code..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.spinner("Agent thinking..."):
        try:
            response = httpx.post(
                "http://localhost:8000/api/chat",
                json={
                    "message": prompt,
                    "session_id": st.session_state.session_id,
                    "machine": machine,
                },
                timeout=30,
            )
            data = response.json()
            agent_text = data.get("message", "Something went wrong.")
            sources = data.get("sources", [])
            escalated = data.get("escalated", False)
            intent = data.get("intent", "general")
            ticket = data.get("ticket")

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": agent_text,
                    "sources": sources,
                }
            )
            with st.chat_message("assistant"):
                st.write(agent_text)
                st.caption(f"Detected Intent: {intent}")
                if sources:
                    with st.expander(f"Based on {len(sources)} KB records"):
                        for source in sources:
                            st.caption(f"- {source}")
                if escalated:
                    st.warning("Escalated to human engineer")
                if ticket:
                    st.info(f"Ticket created: {ticket['ticket_id']}")
        except Exception as exc:
            st.error(f"Agent error: {exc}")
            st.info("Make sure the FastAPI backend is running: uvicorn app.main:app --reload")
