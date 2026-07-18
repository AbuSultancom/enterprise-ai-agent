"""Knowledge store for company documents.

Two retrieval modes:
- semantic search (cosine similarity over embeddings) when an embedding
  provider is available
- keyword search as automatic fallback
Documents are persisted as JSON on disk; embeddings are cached inside them.
"""
from __future__ import annotations

import json
import math
import os
import re
import uuid
from dataclasses import dataclass, asdict, field

DB_PATH = os.getenv("MEMORY_DB_PATH",
                     os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                  "data", "knowledge.json"))


@dataclass
class Document:
    id: str
    title: str
    content: str
    embedding: list[float] | None = field(default=None)


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(x * x for x in b)) or 1e-9
    return dot / (na * nb)


class KnowledgeStore:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        self._docs: dict[str, Document] = {}
        self._load()

    def _load(self):
        if os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as f:
                for d in json.load(f):
                    self._docs[d["id"]] = Document(**d)

    def _save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump([asdict(d) for d in self._docs.values()], f, ensure_ascii=False, indent=2)

    def add(self, title: str, content: str, embedding: list[float] | None = None) -> Document:
        doc = Document(id=str(uuid.uuid4())[:8], title=title, content=content, embedding=embedding)
        self._docs[doc.id] = doc
        self._save()
        return doc

    def delete(self, doc_id: str) -> bool:
        if self._docs.pop(doc_id, None):
            self._save()
            return True
        return False

    def list(self) -> list[Document]:
        return list(self._docs.values())

    def search_keyword(self, query: str, top_k: int = 3) -> list[Document]:
        terms = set(re.findall(r"\w+", query.lower()))
        scored = []
        for doc in self._docs.values():
            text = f"{doc.title} {doc.content}".lower()
            score = sum(text.count(t) for t in terms)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:top_k]]

    def search_semantic(self, query_embedding: list[float], top_k: int = 3) -> list[Document]:
        scored = [
            (_cosine(query_embedding, d.embedding), d)
            for d in self._docs.values() if d.embedding
        ]
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for score, d in scored[:top_k] if score > 0.25]

    async def search(self, query: str, gateway=None, top_k: int = 3) -> list[Document]:
        """Semantic search when embeddings are available, else keyword fallback."""
        if gateway is not None:
            vectors = await gateway.embed([query])
            if vectors:
                docs = self.search_semantic(vectors[0], top_k)
                if docs:
                    return docs
        return self.search_keyword(query, top_k)

    async def embed_document(self, doc: Document, gateway) -> None:
        vectors = await gateway.embed([f"{doc.title}\n{doc.content[:4000]}"])
        if vectors:
            doc.embedding = vectors[0]
            self._save()
