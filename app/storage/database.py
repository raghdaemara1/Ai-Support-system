import os
from functools import lru_cache

from app.models.agent_models import Ticket


class _InMemoryDatabase:
    def __init__(self):
        self._tickets: dict[str, Ticket] = {}
        self._alarms: list[dict] = []

    def save_ticket(self, ticket: Ticket) -> None:
        self._tickets[ticket.ticket_id] = ticket

    def get_alarm(self, alarm_code: str, machine: str | None = None) -> dict | None:
        for alarm in self._alarms:
            if str(alarm.get("alarm_id")) != str(alarm_code):
                continue
            if machine and alarm.get("machine") != machine:
                continue
            return alarm
        return None

    def get_alarms_for_machine(self, machine: str) -> list[dict]:
        return [a for a in self._alarms if a.get("machine") == machine]

    @property
    def alarms(self):
        return self._alarms


class _MongoDatabase:
    def __init__(self, uri: str, db_name: str):
        from pymongo import MongoClient

        self.client = MongoClient(uri)
        self.db = self.client[db_name]
        self.tickets = self.db["tickets"]
        self.alarms = self.db["alarms"]

    def save_ticket(self, ticket: Ticket) -> None:
        self.tickets.insert_one(ticket.model_dump())

    def get_alarm(self, alarm_code: str, machine: str | None = None) -> dict | None:
        query = {"alarm_id": str(alarm_code)}
        if machine:
            query["machine"] = machine
        return self.alarms.find_one(query)

    def get_alarms_for_machine(self, machine: str) -> list[dict]:
        return list(self.alarms.find({"machine": machine}))


@lru_cache(maxsize=1)
def get_database():
    uri = os.environ.get("MONGODB_URI")
    db_name = os.environ.get("MONGODB_DATABASE", "support_agent_demo")

    if uri:
        try:
            return _MongoDatabase(uri=uri, db_name=db_name)
        except Exception:
            return _InMemoryDatabase()

    return _InMemoryDatabase()
