from app.agent.rag_pipeline import RAGPipeline
from app.storage.database import get_database


async def ingest_from_url(tenant_id: str, url: str) -> None:
    """Ingest knowledge from a URL into a tenant's knowledge base."""
    from app.rag.ingestion import ingest_documents
    if url:
        sources = [{"type": "url", "url": url, "source_name": url}]
        await ingest_documents(tenant_id=tenant_id, sources=sources)


def build_kb_from_alarms(machine: str | None = None) -> None:
    db = get_database()
    rag = RAGPipeline()

    if machine:
        alarms = db.get_alarms_for_machine(machine)
    else:
        alarms = list(getattr(db, "alarms", []))

    print(f"Building KB from {len(alarms)} alarm records...")

    for alarm in alarms:
        text = (
            f"Alarm {alarm.get('alarm_id', '')}: {alarm.get('description', '')}. "
            f"Cause: {alarm.get('cause', 'unknown')}. "
            f"Action: {alarm.get('action', 'unknown')}."
        )
        metadata = {
            "alarm_id": str(alarm.get("alarm_id", "")),
            "description": str(alarm.get("description", ""))[:200],
            "cause": str(alarm.get("cause") or "")[:200],
            "action": str(alarm.get("action") or "")[:200],
            "machine": str(alarm.get("machine", "")),
            "reason_1": str(alarm.get("reason_level_1", "")),
        }
        record_id = f"{alarm.get('machine', 'x')}_{alarm.get('alarm_id', '')}"
        rag.add_record(record_id, text, metadata)

    print(f"Done. Total KB records: {rag.count()}")


if __name__ == "__main__":
    build_kb_from_alarms()
