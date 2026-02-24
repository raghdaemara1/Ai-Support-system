import email as email_lib
import imaplib
import os
import smtplib
from email.mime.text import MIMEText

from app.agent.support_agent import SupportAgent
from app.storage.session import SessionManager

_session_manager = SessionManager()
_agent: SupportAgent | None = None


def _get_agent() -> SupportAgent:
    global _agent
    if _agent is None:
        _agent = SupportAgent()
    return _agent


async def poll_inbox_async() -> None:
    email_address = os.environ.get("EMAIL_ADDRESS")
    email_password = os.environ.get("EMAIL_APP_PASSWORD")
    if not email_address or not email_password:
        return

    mail = imaplib.IMAP4_SSL("imap.gmail.com")
    mail.login(email_address, email_password)
    mail.select("inbox")

    _, message_ids = mail.search(None, "UNSEEN")
    if not message_ids or not message_ids[0]:
        mail.logout()
        return

    for msg_id in message_ids[0].split():
        _, msg_data = mail.fetch(msg_id, "(RFC822)")
        raw = msg_data[0][1]
        msg = email_lib.message_from_bytes(raw)

        sender = msg.get("From", "")
        subject = msg.get("Subject") or "Support Request"
        body = _get_text_body(msg)

        session_id = f"email_{sender.split('<')[-1].strip('>')}"
        session = _session_manager.get_or_create(session_id=session_id, channel="email")

        response = await _get_agent().respond(message=f"Subject: {subject}\n\n{body}", session=session)

        _send_reply(to=sender, subject=f"Re: {subject}", body=response.content)
        mail.store(msg_id, "+FLAGS", "\\Seen")

    mail.logout()


def poll_inbox() -> None:
    import asyncio

    asyncio.run(poll_inbox_async())


def _get_text_body(msg) -> str:
    if msg.is_multipart():
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                payload = part.get_payload(decode=True)
                if payload is not None:
                    return payload.decode("utf-8", errors="ignore")
        return ""

    payload = msg.get_payload(decode=True)
    if payload is None:
        return ""
    return payload.decode("utf-8", errors="ignore")


def _send_reply(to: str, subject: str, body: str) -> None:
    email_address = os.environ.get("EMAIL_ADDRESS")
    email_password = os.environ.get("EMAIL_APP_PASSWORD")
    if not email_address or not email_password:
        return

    reply = MIMEText(body)
    reply["Subject"] = subject
    reply["From"] = email_address
    reply["To"] = to

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(email_address, email_password)
        server.sendmail(email_address, to, reply.as_string())
