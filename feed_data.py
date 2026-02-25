import asyncio
from app.rag.ingestion import ingest_documents

async def main():
    docs = [
        {"type": "text", "content": "Alarm code 2008 means the main inverter on the KHS filler is overheating and requires an immediate hard shutdown. Let the machine cool down for 15 minutes before restarting.", "source_name": "KHS_Manual"}
    ]
    await ingest_documents("obeikan", docs)
    print("Ingested mock document!")

asyncio.run(main())
