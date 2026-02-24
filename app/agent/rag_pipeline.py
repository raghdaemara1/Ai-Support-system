import os

from app.models.agent_models import KBSearchResult


class RAGPipeline:
    MODEL_NAME = "all-MiniLM-L6-v2"
    COLLECTION = "support_kb"

    def __init__(self):
        self.chroma_dir = os.environ.get("CHROMA_PERSIST_DIR", "./chroma_db")
        self._memory_records: list[tuple[str, str, dict]] = []
        self._use_chroma = False

        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            self.model = SentenceTransformer(self.MODEL_NAME)
            client = chromadb.PersistentClient(path=self.chroma_dir)
            self.collection = client.get_or_create_collection(
                name=self.COLLECTION,
                metadata={"hnsw:space": "cosine"},
            )
            self._use_chroma = True
        except Exception:
            self.model = None
            self.collection = None

    def search(self, query: str, machine: str | None = None, top_k: int = 3) -> list[KBSearchResult]:
        if self._use_chroma and self.model and self.collection:
            vector = self.model.encode(query).tolist()
            where = {"machine": machine} if machine else None
            results = self.collection.query(
                query_embeddings=[vector],
                n_results=top_k,
                where=where,
                include=["metadatas", "distances", "documents"],
            )

            output: list[KBSearchResult] = []
            for meta, dist, doc in zip(
                results.get("metadatas", [[]])[0],
                results.get("distances", [[]])[0],
                results.get("documents", [[]])[0],
            ):
                output.append(
                    KBSearchResult(
                        alarm_id=meta.get("alarm_id"),
                        description=meta.get("description", doc[:100]),
                        cause=meta.get("cause"),
                        action=meta.get("action"),
                        machine=meta.get("machine"),
                        score=round(1 - dist, 3),
                    )
                )
            return output

        query_lower = query.lower()
        scored: list[tuple[float, tuple[str, str, dict]]] = []
        for rec in self._memory_records:
            _, text, meta = rec
            if machine and meta.get("machine") != machine:
                continue
            overlap = sum(1 for token in query_lower.split() if token in text.lower())
            if overlap > 0:
                score = min(0.95, 0.4 + overlap / 10)
                scored.append((score, rec))

        scored.sort(key=lambda x: x[0], reverse=True)
        output: list[KBSearchResult] = []
        for score, (_, text, meta) in scored[:top_k]:
            output.append(
                KBSearchResult(
                    alarm_id=meta.get("alarm_id"),
                    description=meta.get("description", text[:100]),
                    cause=meta.get("cause"),
                    action=meta.get("action"),
                    machine=meta.get("machine"),
                    score=round(score, 3),
                )
            )
        return output

    def add_record(self, record_id: str, text: str, metadata: dict) -> None:
        if self._use_chroma and self.model and self.collection:
            vector = self.model.encode(text).tolist()
            self.collection.upsert(
                ids=[record_id],
                embeddings=[vector],
                documents=[text],
                metadatas=[metadata],
            )
            return

        self._memory_records.append((record_id, text, metadata))

    def count(self) -> int:
        if self._use_chroma and self.collection:
            return int(self.collection.count())
        return len(self._memory_records)
