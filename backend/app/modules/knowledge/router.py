from __future__ import annotations

import hashlib
import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError, not_found
from app.modules.audit import service as audit
from app.modules.content.models import Destination
from app.modules.identity.deps import require
from app.modules.identity.service import Principal
from app.modules.knowledge import ingestion
from app.modules.knowledge.models import KgEntity, KgRelation, KnowledgeChunk, KnowledgeDocument
from app.modules.knowledge.retrieval import retrieve

router = APIRouter(prefix="/api/bureau/knowledge", tags=["knowledge"])
public_router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])

RIGHTS = ("public_domain", "cc_by", "cc_by_sa", "open_government", "licensed", "bureau_owned", "permission_granted",
          "restricted", "unknown")
Classification = Literal["public", "internal", "restricted", "sacred"]


def doc_out(d: KnowledgeDocument, full: bool = False) -> dict:
    out = {"id": str(d.id), "title": d.title, "author": d.author, "publisher": d.publisher, "published_on": d.published_on,
           "original_language": d.original_language, "detected_language": d.detected_language,
           "rights_status": d.rights_status, "license_note": d.license_note, "url": d.url, "citation": d.citation,
           "access_classification": d.access_classification, "verification_status": d.verification_status,
           "reviewed_at": d.reviewed_at.isoformat() if d.reviewed_at else None, "status": d.status, "version": d.version,
           "supersedes_id": str(d.supersedes_id) if d.supersedes_id else None,
           "revalidate_on": d.revalidate_on.isoformat() if d.revalidate_on else None,
           "destination_ids": [str(x) for x in d.destination_ids or []], "injection_flags": d.injection_flags,
           "scan_status": d.scan_status, "processing_error": d.processing_error, "retrieval_check": d.retrieval_check,
           "is_synthetic": d.is_synthetic, "consent_reference": d.consent_reference,
           "custodian_approval_ref": d.custodian_approval_ref, "created_at": d.created_at.isoformat()}
    if full:
        out["status_history"] = d.status_history
        out["text_preview"] = (d.extracted_text or "")[:3000]
        out["chunk_count"] = None
    return out


def _doc(db: Session, ident: uuid.UUID) -> KnowledgeDocument:
    d = db.get(KnowledgeDocument, ident)
    if d is None:
        raise not_found("Document")
    return d


def _dest_ids(db: Session, slugs: str | None) -> list[uuid.UUID]:
    if not slugs:
        return []
    wanted = [s.strip() for s in slugs.split(",") if s.strip()]
    found = {d.slug: d.id for d in db.execute(select(Destination).where(Destination.slug.in_(wanted))).scalars()}
    if missing := sorted(set(wanted) - set(found)):
        raise AppError(422, "unknown_destinations", "Unknown destination slugs", missing)
    return list(found.values())


@router.post("/documents", status_code=201)
async def upload(request: Request, file: UploadFile = File(...), title: str = Form(..., min_length=3, max_length=400),
                 author: str | None = Form(None), publisher: str | None = Form(None),
                 published_on: str | None = Form(None), original_language: str = Form("und"),
                 rights_status: str = Form("unknown"), license_note: str | None = Form(None),
                 url: str | None = Form(None), citation: str | None = Form(None),
                 access_classification: Classification = Form("internal"),
                 destination_slugs: str | None = Form(None), consent_reference: str | None = Form(None),
                 custodian_approval_ref: str | None = Form(None), is_synthetic: bool = Form(False),
                 supersedes_id: uuid.UUID | None = Form(None),
                 p: Principal = Depends(require("knowledge.upload")), db: Session = Depends(get_db)):
    if rights_status not in RIGHTS:
        raise AppError(422, "invalid_rights", "Unknown rights status", list(RIGHTS))
    if url and not url.startswith(("https://", "http://")):
        raise AppError(422, "invalid_url", "Source URL must be http(s).")  # stored as metadata only, never fetched
    data = await file.read(ingestion.MAX_DOC_BYTES + 1)
    if len(data) > ingestion.MAX_DOC_BYTES:
        raise AppError(413, "file_too_large", "Documents must be at most 20 MB.")
    mime = ingestion.sniff_mime(data, file.content_type, file.filename)
    version = 1
    if supersedes_id:
        prev = _doc(db, supersedes_id)
        version = prev.version + 1
    doc = KnowledgeDocument(title=title, author=author, publisher=publisher, published_on=published_on,
                            original_language=original_language, rights_status=rights_status, license_note=license_note,
                            url=url, citation=citation, access_classification=access_classification,
                            destination_ids=_dest_ids(db, destination_slugs), consent_reference=consent_reference,
                            custodian_approval_ref=custodian_approval_ref, is_synthetic=is_synthetic, mime=mime,
                            sha256=hashlib.sha256(data).hexdigest(), uploaded_by=p.id, version=version,
                            supersedes_id=supersedes_id)
    ingestion.transition(doc, "uploaded", p.id)
    db.add(doc)
    db.flush()
    ingestion.process_upload(doc, data)
    audit.record(db, action="knowledge.upload", resource_type="knowledge_document", resource_id=doc.id, actor=p,
                 request=request, changes={"title": title, "classification": access_classification, "status": doc.status,
                                           "injection_flags": len(doc.injection_flags)})
    db.commit()
    return doc_out(doc, full=True)


@router.get("/documents")
def list_docs(status: str | None = None, p: Principal = Depends(require("knowledge.upload", "knowledge.review", any_of=True)),
              db: Session = Depends(get_db)):
    stmt = select(KnowledgeDocument).order_by(KnowledgeDocument.created_at.desc()).limit(300)
    if status:
        stmt = stmt.where(KnowledgeDocument.status == status)
    if not p.has("knowledge.read_restricted"):
        stmt = stmt.where(KnowledgeDocument.access_classification.in_(["public", "internal"]))
    return [doc_out(d) for d in db.execute(stmt).scalars()]


@router.get("/documents/{ident}")
def get_doc(ident: uuid.UUID, p: Principal = Depends(require("knowledge.upload", "knowledge.review", any_of=True)),
            db: Session = Depends(get_db)):
    d = _doc(db, ident)
    if d.access_classification in ("restricted", "sacred") and not p.has("knowledge.read_restricted"):
        raise not_found("Document")
    out = doc_out(d, full=True)
    out["chunk_count"] = len(db.execute(select(KnowledgeChunk.id).where(KnowledgeChunk.document_id == d.id)).all())
    return out


class ReviewIn(BaseModel):
    title: str | None = Field(default=None, max_length=400)
    author: str | None = None
    publisher: str | None = None
    published_on: str | None = None
    original_language: str | None = None
    rights_status: str | None = None
    license_note: str | None = None
    citation: str | None = None
    access_classification: Classification | None = None
    verification_status: Literal["unverified", "verified", "disputed"] | None = None
    revalidate_on: date | None = None
    destination_slugs: str | None = None
    custodian_approval_ref: str | None = None
    note: str = Field(default="", max_length=500)


@router.patch("/documents/{ident}")
def review_doc(ident: uuid.UUID, body: ReviewIn, request: Request, p: Principal = Depends(require("knowledge.review")),
               db: Session = Depends(get_db)):
    d = _doc(db, ident)
    if d.status in ("published",) and body.access_classification and body.access_classification != d.access_classification:
        raise AppError(409, "withdraw_first", "Withdraw the document before changing its classification.")
    data = body.model_dump(exclude_unset=True, exclude={"note", "destination_slugs"})
    if "rights_status" in data and data["rights_status"] not in RIGHTS:
        raise AppError(422, "invalid_rights", "Unknown rights status", list(RIGHTS))
    for k, v in data.items():
        setattr(d, k, v)
    if body.destination_slugs is not None:
        d.destination_ids = _dest_ids(db, body.destination_slugs)
    d.reviewer_id, d.reviewed_at = p.id, utcnow()
    ingestion.transition(d, d.status, p.id, body.note or "metadata reviewed")
    audit.record(db, action="knowledge.review", resource_type="knowledge_document", resource_id=d.id, actor=p,
                 request=request, changes={k: str(v)[:100] for k, v in data.items()})
    db.commit()
    return doc_out(d, full=True)


@router.post("/documents/{ident}/approve")
def approve(ident: uuid.UUID, request: Request, p: Principal = Depends(require("knowledge.publish")),
            db: Session = Depends(get_db)):
    """Editorial approval -> chunk + embed + index -> automatic retrieval check."""
    d = _doc(db, ident)
    if d.status != "in_review":
        raise AppError(409, "invalid_state", f"Only documents in review can be approved (status: {d.status}).")
    if d.uploaded_by == p.id:
        raise AppError(403, "four_eyes", "A different person must approve the document you uploaded.")
    if d.reviewed_at is None:
        raise AppError(409, "not_reviewed", "Metadata review is required before approval.")
    if d.rights_status in ("unknown", "restricted") and d.access_classification == "public":
        raise AppError(422, "rights_unclear", "Public documents need cleared rights.")
    if d.access_classification in ("restricted", "sacred") and not d.custodian_approval_ref:
        raise AppError(422, "custodian_approval_required", "Restricted or sacred material needs a custodian approval reference.")
    if d.injection_flags and d.access_classification == "public":
        # Flagged text may still be legitimate (e.g. a document about AI); reviewer must acknowledge via note.
        if not any("injection acknowledged" in (h.get("note") or "") for h in d.status_history or []):
            raise AppError(409, "injection_flags_unacknowledged",
                           "Instruction-like text was detected. Review it and record 'injection acknowledged' in a review note.")
    d.approved_by = p.id
    n = ingestion.index_document(db, d)
    ingestion.transition(d, "indexed", p.id, f"{n} chunks")
    hits = retrieve(db, d.title, principal=p, k=5, include_unpublished=True)
    found = any(h.document_id == d.id for h in hits)
    d.retrieval_check = {"query": d.title, "found_in_top5": found, "checked_at": utcnow().isoformat(), "chunks": n}
    audit.record(db, action="knowledge.approve", resource_type="knowledge_document", resource_id=d.id, actor=p,
                 request=request, changes={"chunks": n, "retrieval_check": found})
    db.commit()
    return doc_out(d, full=True)


@router.post("/documents/{ident}/publish")
def publish(ident: uuid.UUID, request: Request, p: Principal = Depends(require("knowledge.publish")),
            db: Session = Depends(get_db)):
    d = _doc(db, ident)
    if d.status != "indexed":
        raise AppError(409, "invalid_state", "Only indexed documents can be published.")
    db.execute(update(KnowledgeChunk).where(KnowledgeChunk.document_id == d.id).values(published=True))
    ingestion.transition(d, "published", p.id)
    if d.supersedes_id:
        prev = db.get(KnowledgeDocument, d.supersedes_id)
        if prev and prev.status == "published":
            db.execute(update(KnowledgeChunk).where(KnowledgeChunk.document_id == prev.id).values(published=False))
            ingestion.transition(prev, "superseded", p.id, f"superseded by v{d.version}")
    audit.record(db, action="knowledge.publish", resource_type="knowledge_document", resource_id=d.id, actor=p, request=request)
    db.commit()
    return doc_out(d, full=True)


@router.post("/documents/{ident}/{action}")
def reject_or_withdraw(ident: uuid.UUID, action: Literal["reject", "withdraw"], request: Request,
                       p: Principal = Depends(require("knowledge.publish")), db: Session = Depends(get_db)):
    d = _doc(db, ident)
    db.execute(update(KnowledgeChunk).where(KnowledgeChunk.document_id == d.id).values(published=False))
    ingestion.transition(d, "rejected" if action == "reject" else "withdrawn", p.id)
    audit.record(db, action=f"knowledge.{action}", resource_type="knowledge_document", resource_id=d.id, actor=p,
                 request=request)
    db.commit()
    return doc_out(d)


@router.get("/search")
def staff_search(q: str, p: Principal = Depends(require("knowledge.review", "knowledge.upload", any_of=True)),
                 db: Session = Depends(get_db)):
    hits = retrieve(db, q, principal=p, k=10)
    return [{"chunk_id": str(h.chunk_id), "document": h.doc, "text": h.text[:500], "score": round(h.score, 4),
             "signals": h.signals} for h in hits]


@router.post("/reindex")
def reindex(request: Request, p: Principal = Depends(require("ai.admin")), db: Session = Depends(get_db)):
    """Knowledge-index reconstruction (e.g. after an embedding-model change or a restore)."""
    docs = db.execute(select(KnowledgeDocument).where(KnowledgeDocument.status.in_(["indexed", "published"]))).scalars().all()
    total = 0
    for d in docs:
        total += ingestion.index_document(db, d)
        if d.status == "published":
            db.execute(update(KnowledgeChunk).where(KnowledgeChunk.document_id == d.id).values(published=True))
    audit.record(db, action="knowledge.reindex", resource_type="knowledge_index", resource_id="all", actor=p,
                 request=request, changes={"documents": len(docs), "chunks": total})
    db.commit()
    return {"documents": len(docs), "chunks": total}


# ---------------------------------------------------------------- knowledge graph

class EntityIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9-:]{1,119}$")
    kind: Literal["destination", "person", "period", "artifact", "tradition", "place", "institution"]
    name_i18n: dict[Literal["en", "ti", "am"], str]
    destination_slug: str | None = None
    access_classification: Classification = "public"


class RelationIn(BaseModel):
    subject_key: str
    predicate: str = Field(pattern=r"^[a-z_]{2,60}$")
    object_key: str | None = None
    object_text: str | None = Field(default=None, max_length=500)
    source_document_id: uuid.UUID
    contested: bool = False
    note: str | None = Field(default=None, max_length=500)


@router.post("/graph/entities", status_code=201)
def add_entity(body: EntityIn, request: Request, p: Principal = Depends(require("knowledge.review")),
               db: Session = Depends(get_db)):
    dest = None
    if body.destination_slug:
        dest = db.execute(select(Destination.id).where(Destination.slug == body.destination_slug)).scalar_one_or_none()
    e = KgEntity(key=body.key, kind=body.kind, name_i18n=body.name_i18n, destination_id=dest,
                 access_classification=body.access_classification)
    db.add(e)
    db.flush()
    audit.record(db, action="kg.entity", resource_type="kg_entity", resource_id=body.key, actor=p, request=request)
    db.commit()
    return {"key": e.key}


@router.post("/graph/relations", status_code=201)
def add_relation(body: RelationIn, request: Request, p: Principal = Depends(require("knowledge.review")),
                 db: Session = Depends(get_db)):
    ents = {e.key: e for e in db.execute(select(KgEntity).where(KgEntity.key.in_([body.subject_key, body.object_key or ""]))).scalars()}
    if body.subject_key not in ents or (body.object_key and body.object_key not in ents):
        raise AppError(422, "unknown_entity", "Subject/object entity not found")
    if not body.object_key and not body.object_text:
        raise AppError(422, "missing_object", "Provide object_key or object_text")
    _doc(db, body.source_document_id)
    r = KgRelation(subject_id=ents[body.subject_key].id, predicate=body.predicate,
                   object_id=ents[body.object_key].id if body.object_key else None, object_text=body.object_text,
                   source_document_id=body.source_document_id, contested=body.contested, note=body.note)
    db.add(r)
    audit.record(db, action="kg.relation", resource_type="kg_relation", resource_id=body.subject_key, actor=p,
                 request=request, changes={"predicate": body.predicate, "contested": body.contested})
    db.commit()
    return {"status": "created"}


@public_router.get("/graph/{key}")
def graph(key: str, locale: str = "en", db: Session = Depends(get_db)):
    """Public view: only public entities, and only relations backed by published public documents."""
    e = db.execute(select(KgEntity).where(KgEntity.key == key, KgEntity.access_classification == "public")).scalar_one_or_none()
    if e is None:
        raise not_found("Entity")
    rows = db.execute(select(KgRelation, KnowledgeDocument).join(KnowledgeDocument, KnowledgeDocument.id == KgRelation.source_document_id)
                      .where(KgRelation.subject_id == e.id, KnowledgeDocument.status == "published",
                             KnowledgeDocument.access_classification == "public")).all()
    objs = {o.id: o for o in db.execute(select(KgEntity).where(KgEntity.id.in_([r.object_id for r, _ in rows if r.object_id]))).scalars()}
    claims = []
    for r, d in rows:
        o = objs.get(r.object_id) if r.object_id else None
        if o is not None and o.access_classification != "public":
            continue
        claims.append({"predicate": r.predicate, "object": (o.name_i18n.get(locale) or o.name_i18n.get("en")) if o else r.object_text,
                       "object_key": o.key if o else None, "contested": r.contested, "note": r.note,
                       "source": {"id": str(d.id), "title": d.title, "author": d.author, "published_on": d.published_on}})
    return {"key": e.key, "kind": e.kind, "name": e.name_i18n.get(locale) or e.name_i18n.get("en"), "claims": claims}
