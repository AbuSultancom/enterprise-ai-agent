"""Knowledge base router: list, add, upload, delete documents."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Security, UploadFile
from pydantic import BaseModel

from api.dependencies import audit, require_role
from llm_gateway.gateway import LLMGateway
from memory.store import KnowledgeStore

router = APIRouter(prefix="/v1/knowledge", tags=["Knowledge Base"])

_store: KnowledgeStore | None = None
_gateway: LLMGateway | None = None


def init(store: KnowledgeStore, gateway: LLMGateway) -> None:
    global _store, _gateway
    _store = store
    _gateway = gateway


class DocRequest(BaseModel):
    title: str
    content: str


def _extract_text(filename: str, data: bytes) -> str:
    name = filename.lower()
    if name.endswith((".txt", ".md", ".csv", ".json", ".log")):
        return data.decode("utf-8", errors="replace")
    if name.endswith(".pdf"):
        import io

        from pypdf import PdfReader

        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages)
    if name.endswith(".docx"):
        import io

        import docx  # noqa: E401

        return "\n".join(p.text for p in docx.Document(io.BytesIO(data)).paragraphs)
    raise ValueError(f"Unsupported file type: {filename} (use .txt .md .csv .pdf .docx)")


@router.get("", dependencies=[Depends(require_role("admin", "user"))])
async def list_docs():
    if _store is None:
        raise RuntimeError("Knowledge store not initialized")
    return [
        {"id": d.id, "title": d.title, "has_embedding": bool(d.embedding), "chars": len(d.content)}
        for d in _store.list()
    ]


@router.post("", dependencies=[Depends(require_role("admin"))])
async def add_doc(req: DocRequest):
    if _store is None or _gateway is None:
        raise RuntimeError("Knowledge store or gateway not initialized")
    doc = _store.add(req.title, req.content)
    await _store.embed_document(doc, _gateway)
    return {"id": doc.id, "title": doc.title, "embedded": bool(doc.embedding)}


@router.post("/upload", dependencies=[Depends(require_role("admin"))])
async def upload_doc(file: UploadFile, role: str = Security(require_role("admin"))):
    if _store is None or _gateway is None:
        raise RuntimeError("Knowledge store or gateway not initialized")
    data = await file.read()
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 20 MB)")
    try:
        text = _extract_text(file.filename or "document", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    if not text.strip():
        raise HTTPException(status_code=400, detail="No text could be extracted from this file")

    chunks = [text[i : i + 3000] for i in range(0, len(text), 3000)]
    ids = []
    for i, chunk in enumerate(chunks):
        title = f"{file.filename}" + (f" (part {i + 1}/{len(chunks)})" if len(chunks) > 1 else "")
        doc = _store.add(title, chunk)
        await _store.embed_document(doc, _gateway)
        ids.append(doc.id)

    audit("knowledge_upload", role, {"file": file.filename, "chunks": len(ids)})
    return {"file": file.filename, "chunks": len(ids), "ids": ids}


@router.delete("/{doc_id}", dependencies=[Depends(require_role("admin"))])
async def delete_doc(doc_id: str):
    if _store is None:
        raise RuntimeError("Knowledge store not initialized")
    if not _store.delete(doc_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return {"deleted": doc_id}
