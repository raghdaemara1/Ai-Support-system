import uuid

from app.models.agent_models import Channel, Ticket
from app.storage.database import get_database


class ToolExecutor:
    def __init__(self):
        self.db = get_database()

    def create_ticket(
        self,
        session_id: str,
        channel: str,
        summary: str,
        machine: str | None = None,
        alarm_code: str | None = None,
        priority: str = "medium",
    ) -> Ticket:
        ticket = Ticket(
            ticket_id=f"TKT-{uuid.uuid4().hex[:8].upper()}",
            session_id=session_id,
            channel=Channel(channel),
            summary=summary,
            machine=machine,
            alarm_code=alarm_code,
            priority=priority,
        )
        self.db.save_ticket(ticket)
        return ticket

    def lookup_alarm(self, alarm_code: str, machine: str | None = None) -> dict | None:
        return self.db.get_alarm(alarm_code=alarm_code, machine=machine)
