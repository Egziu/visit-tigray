"""Knowledge ingestion: extraction, language detection, injection screening, chunking, embedding.

Pipeline (docs/KNOWLEDGE_GOVERNANCE.md):
upload -> malware scan -> extraction -> language detection -> metadata review -> editorial approval
-> chunking -> embedding -> indexing -> retrieval check -> publication
"""
from __future__ import annotations

import html
import io
import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.core.ethiopic import fold_for_search, guess_language, nfc, transliterate
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument
from app.modules.tie.embeddings import get_embedder

TEXT_MIMES = {"text/plain", "text/markdown", "text/html"}
PDF_MIME = "application/pdf"
MAX_DOC_BYTES = 20 * 1024 * 1024

# Instruction-like text inside documents (indirect prompt injection). Flagged for the reviewer;
# at answer time all documents are wrapped as untrusted data regardless.
INJECTION_PATTERNS = [
    r"ignore (all |any )?(previous|prior|above) (instructions|prompts?)",
    r"disregard (the )?(system|previous) (prompt|instructions)",
    r"you are now (?:an?|the) ",
    r"\bsystem prompt\b",
    r"\bdeveloper mode\b",
    r"<\s*/?\s*(system|assistant|instructions?)\s*>",
    r"reveal (your|the) (instructions|prompt|secrets?)",
    r"\bact as\b.{0,40}\b(admin|administrator|root)\b",
    r"(call|invoke|use) the tool",
]


def sniff_mime(data: bytes, declared: str | None, filename: str | None) -> str:
    if data.startswith(b"%PDF-"):
        return PDF_MIME
    name = (filename or "").lower()
    if name.endswith(".md"):
        return "text/markdown"
    if name.endswith((".html", ".htm")) or (declared or "").startswith("text/html"):
        return "text/html"
    try:
        data[:4096].decode("utf-8")
        return "text/plain"
    except UnicodeDecodeError as exc:
        raise AppError(415, "unsupported_document", "Upload UTF-8 text, Markdown, HTML or PDF documents.") from exc


def extract_text(data: bytes, mime: str) -> str:
    if mime == PDF_MIME:
        from pypdf import PdfReader

        try:
            reader = PdfReader(io.BytesIO(data))
            if reader.is_encrypted:
                raise AppError(422, "encrypted_pdf", "Encrypted PDFs cannot be ingested.")
            text = "\n\n".join((p.extract_text() or "") for p in reader.pages[:2000])
        except AppError:
            raise
        except Exception as exc:  # noqa: BLE001 - malformed PDFs
            raise AppError(422, "pdf_unreadable", "The PDF could not be read.") from exc
        if len(text.strip()) < 20:
            # Scanned PDF: needs OCR. OCR engine integration (Tesseract with amh/tir models) is a
            # documented, unresolved dependency — see docs/LOCAL_AI_ARCHITECTURE.md §OCR.
            raise AppError(422, "ocr_required", "This PDF contains no text layer; OCR is required (not yet available).")
        return nfc(text)
    raw = data.decode("utf-8", errors="replace")
    if mime == "text/html":
        raw = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", raw)
        raw = re.sub(r"(?s)<[^>]+>", " ", raw)
        raw = html.unescape(raw)
    return nfc(raw)


def screen_for_injection(text: str) -> list[str]:
    flags = []
    low = text.lower()
    for pat in INJECTION_PATTERNS:
        m = re.search(pat, low)
        if m:
            flags.append(m.group(0)[:80])
    return flags


def _tail_words(text: str, max_chars: int) -> str:
    """Last ~max_chars of text, starting at a word boundary (never mid-word)."""
    if len(text) <= max_chars:
        return text
    tail = text[-max_chars:]
    cut = re.search(r"\s", tail)
    return tail[cut.end():] if cut else ""


def chunk_text(text: str, target_chars: int = 900, overlap_chars: int = 150) -> list[str]:
    """Paragraph-aware chunking with overlap. Ethiopic sentence ends (።) are respected."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(p) > target_chars * 1.5:
            sentences = re.split(r"(?<=[.!?።፧])\s+", p)
        else:
            sentences = [p]
        for s in sentences:
            if buf and len(buf) + len(s) + 1 > target_chars:
                chunks.append(buf.strip())
                buf = _tail_words(buf, overlap_chars) + " " + s if overlap_chars else s
            else:
                buf = f"{buf}\n\n{s}" if buf else s
    if buf.strip():
        chunks.append(buf.strip())
    return chunks


def transition(doc: KnowledgeDocument, status: str, actor_id=None, note: str | None = None) -> None:
    doc.status = status
    doc.status_history = [*(doc.status_history or []), {"status": status, "at": utcnow().isoformat(),
                                                         "by": str(actor_id) if actor_id else None, "note": note}]


def process_upload(doc: KnowledgeDocument, data: bytes) -> None:
    """Scan + extract + detect language + screen. Leaves the document in 'in_review' or 'failed'."""
    from app.modules.media.service import scan_bytes

    scan, detail = scan_bytes(data)
    doc.scan_status = scan
    if scan == "infected":
        doc.processing_error = detail
        transition(doc, "rejected", note="malware detected")
        return
    try:
        text = extract_text(data, doc.mime)
    except AppError as e:
        doc.processing_error = e.message
        transition(doc, "failed", note=e.code)
        return
    doc.extracted_text = text
    doc.detected_language = guess_language(text[:5000])
    doc.injection_flags = screen_for_injection(text)
    transition(doc, "in_review", note="extracted")


def index_document(db: Session, doc: KnowledgeDocument, mode: str = "fully_local") -> int:
    """Chunk + embed + store. Chunks stay unpublished until the document is published."""
    if not doc.extracted_text:
        raise AppError(409, "no_text", "Document has no extracted text.")
    db.execute(delete(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id))
    pieces = chunk_text(doc.extracted_text)
    embedder = get_embedder()
    header = f"{doc.title}. "
    vectors = embedder.embed([header + p for p in pieces], mode=mode)
    for i, (p, vec) in enumerate(zip(pieces, vectors, strict=True)):
        db.add(KnowledgeChunk(document_id=doc.id, ordinal=i, text=p,
                              folded=fold_for_search(f"{doc.title} {p} {transliterate(p)}"),
                              language=guess_language(p) if guess_language(p) != "und" else (doc.detected_language or "und"),
                              embedding=vec, embedding_model=embedder.name,
                              access_classification=doc.access_classification,
                              destination_ids=list(doc.destination_ids or []), published=False))
    db.flush()
    return len(pieces)
