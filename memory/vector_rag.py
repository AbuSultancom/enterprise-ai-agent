"""Hybrid RAG Search Engine.
Combines BM25 keyword matching with Vector Embeddings cosine similarity and Reranking.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, List, Tuple


@dataclass
class DocumentChunk:
    doc_id: str
    filename: str
    text: str
    chunk_index: int
    embedding: list[float] | None = None


class HybridRAGSearch:
    """Hybrid Search engine mixing BM25 and Vector Embeddings."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.chunks: List[DocumentChunk] = []
        self.k1 = k1
        self.b = b

    def add_chunks(self, chunks: List[DocumentChunk]) -> None:
        self.chunks.extend(chunks)

    def clear() -> None:
        self.chunks = []

    def _tokenize(self, text: str) -> list[str]:
        return [w.lower() for w in re.findall(r'\w+', text)]

    def bm25_search(self, query: str, top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        if not self.chunks:
            return []

        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        N = len(self.chunks)
        doc_tokens_list = [self._tokenize(c.text) for c in self.chunks]
        avgdl = sum(len(d) for d in doc_tokens_list) / N if N > 0 else 1.0

        scores = []
        for idx, chunk in enumerate(self.chunks):
            doc_tokens = doc_tokens_list[idx]
            doc_len = len(doc_tokens)
            score = 0.0

            for q_term in query_tokens:
                # Calculate document frequency
                df = sum(1 for d in doc_tokens_list if q_term in d)
                if df == 0:
                    continue
                idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                tf = doc_tokens.count(q_term)
                denom = tf + self.k1 * (1 - self.b + self.b * (doc_len / avgdl))
                score += idf * (tf * (self.k1 + 1)) / denom if denom > 0 else 0.0

            scores.append((chunk, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @staticmethod
    def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
        if not vec1 or not vec2 or len(vec1) != len(vec2):
            return 0.0
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def vector_search(self, query_embedding: list[float], top_k: int = 5) -> List[Tuple[DocumentChunk, float]]:
        if not self.chunks or not query_embedding:
            return []

        scores = []
        for chunk in self.chunks:
            if chunk.embedding:
                sim = self.cosine_similarity(query_embedding, chunk.embedding)
                scores.append((chunk, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def hybrid_search(
        self,
        query: str,
        query_embedding: list[float] | None = None,
        top_k: int = 5,
        alpha: float = 0.5
    ) -> List[Tuple[DocumentChunk, float]]:
        """Hybrid RAG combining BM25 and Vector search normalized scores."""
        bm25_results = self.bm25_search(query, top_k=top_k * 2)
        vec_results = self.vector_search(query_embedding, top_k=top_k * 2) if query_embedding else []

        combined_scores: dict[str, float] = {}
        chunk_map: dict[str, DocumentChunk] = {}

        # Normalize BM25
        max_bm25 = max([s for _, s in bm25_results], default=1.0) or 1.0
        for chunk, score in bm25_results:
            cid = f"{chunk.doc_id}_{chunk.chunk_index}"
            chunk_map[cid] = chunk
            combined_scores[cid] = combined_scores.get(cid, 0.0) + (1.0 - alpha) * (score / max_bm25)

        # Vector score is already 0..1
        for chunk, score in vec_results:
            cid = f"{chunk.doc_id}_{chunk.chunk_index}"
            chunk_map[cid] = chunk
            combined_scores[cid] = combined_scores.get(cid, 0.0) + alpha * max(0.0, score)

        ranked = [(chunk_map[cid], score) for cid, score in combined_scores.items()]
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked[:top_k]
