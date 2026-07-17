"""Lightweight knowledge store for company documents (RAG-ready).

MVP: keyword-based retrieval over a JSON document store, persisted on disk.
Swap `search()` with Chroma/Qdrant embeddings for semantic search later.
"""
from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, asdict

DB_PATH = os.getenv("MEMORY_DB_PATH", "/data/knowledge.json")


@dataclass
class Document:
    id: str
    title: str
    content: str


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

    def add(self, title: str, content: str) -> Document:
        doc = Document(id=str(uuid.uuid4())[:8], title=title, content=content)
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

    def search(self, query: str, top_k: int = 3) -> list[Document]:
        terms = set(re.findall(r"\w+", query.lower()))
        scored = []
        for doc in self._docs.values():
            text = f"{doc.title} {doc.content}".lower()
            score = sum(text.count(t) for t in terms)
            if score:
                scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [d for _, d in scored[:top_k]]
