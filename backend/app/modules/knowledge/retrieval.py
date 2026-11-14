"""Hybrid, permission-aware retrieval.

Stages:
1. Clearance: the caller's permissions determine allowed access classifications. The filter is
   part of every SQL query — restricted rows are never fetched.
2. Query expansion: place aliases (Aksum/Axum/አክሱም) matching the query add the destination's
   names in other scripts/languages, giving cross-lingual recall for named places.
3. Candidates: pgvector cosine (HNSW) + PostgreSQL full-text ('simple' config over folded text)
   + trigram similarity, each limited, optionally filtered to destinations / a geographic radius.
4. Fusion: reciprocal-rank fusion (k=60).
5. Rerank: lexical-overlap reranker (term coverage of folded query tokens) blended with RRF.
   A cross-encoder reranker can replace ``rerank`` via the provider registry (not bundled).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.ethiopic import fold_for_search, tokens, transliterate
from app.modules.content.models import Destination, PlaceAlias
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument
from app.modules.tie.embeddings import get_embedder

RRF_K = 60


def clearance_for(principal) -> set[str]:
    allowed = {"public"}
    if principal is not None:
        if principal.has("knowledge.read_internal"):
            allowed.add("internal")
        if principal.has("knowledge.read_restricted"):
            allowed |= {"internal", "restricted", "sacred"}
    return allowed


@dataclass
class Hit:
    chunk_id: uuid.UUID
    document_id: uuid.UUID
    text: str
    language: str
    score: float
    signals: dict = field(default_factory=dict)
    doc: dict = field(default_factory=dict)


def expand_query(db: Session, query: str) -> tuple[str, list[uuid.UUID], set[str], set[str]]:
    """Return (expanded query, destination ids, query tokens naming a place, all alias tokens of those places)."""
    q_tokens = set(tokens(query)) | set(tokens(transliterate(query)))
    if not q_tokens:
        return query, [], set(), set()
    rows = db.execute(select(PlaceAlias.destination_id, PlaceAlias.normalized)).all()
    dest_ids, triggers = set(), set()
    for did, norm in rows:
        alias_toks = set(tokens(norm or "")) | set(tokens(transliterate(norm or "")))
        if alias_toks & q_tokens:
            dest_ids.add(did)
            triggers |= alias_toks & q_tokens
    if not dest_ids:
        return query, [], set(), set()
    names = db.execute(select(PlaceAlias.name).where(PlaceAlias.destination_id.in_(dest_ids))).scalars().all()
    alias_tokens = {t for n in names for t in set(tokens(n)) | set(tokens(transliterate(n)))}
    return query + " " + " ".join(sorted(set(names))), sorted(dest_ids), triggers, alias_tokens


def retrieve(db: Session, query: str, *, principal=None, k: int = 8, destination_ids: list[uuid.UUID] | None = None,
             near: tuple[float, float, float] | None = None, mode: str = "fully_local",
             include_unpublished: bool = False) -> list[Hit]:
    allowed = sorted(clearance_for(principal))
    expanded, alias_dests, place_terms, alias_tokens = expand_query(db, query)
    folded = fold_for_search(expanded + " " + transliterate(expanded))
    qvec = get_embedder().embed([expanded], mode=mode)[0]

    base = select(KnowledgeChunk.id).where(KnowledgeChunk.access_classification.in_(allowed))
    if not include_unpublished:
        base = base.where(KnowledgeChunk.published.is_(True))
    if destination_ids:
        base = base.where(KnowledgeChunk.destination_ids.overlap(destination_ids))
    if near is not None:
        lat, lng, km = near
        nearby = select(Destination.id).where(func.ST_DWithin(
            Destination.location, func.ST_GeogFromText(f"SRID=4326;POINT({float(lng)} {float(lat)})"), km * 1000))
        base = base.where(KnowledgeChunk.destination_ids.overlap(func.array(nearby.scalar_subquery())))

    vec_ids = db.execute(base.order_by(KnowledgeChunk.embedding.cosine_distance(qvec)).limit(30)).scalars().all()
    lex_ids = db.execute(base.where(or_(KnowledgeChunk.tsv.op("@@")(func.to_tsquery("simple", _or_query(folded))),
                                        func.similarity(KnowledgeChunk.folded, folded) > 0.05))
                         .order_by(func.ts_rank_cd(KnowledgeChunk.tsv, func.to_tsquery("simple", _or_query(folded))).desc(),
                                   func.similarity(KnowledgeChunk.folded, folded).desc())
                         .limit(30)).scalars().all()

    fused: dict[uuid.UUID, float] = {}
    signals: dict[uuid.UUID, dict] = {}
    for rank, cid in enumerate(vec_ids):
        fused[cid] = fused.get(cid, 0) + 1 / (RRF_K + rank + 1)
        signals.setdefault(cid, {})["vector_rank"] = rank + 1
    for rank, cid in enumerate(lex_ids):
        fused[cid] = fused.get(cid, 0) + 1 / (RRF_K + rank + 1)
        signals.setdefault(cid, {})["lexical_rank"] = rank + 1
    if not fused:
        return []
    rows = db.execute(select(KnowledgeChunk, KnowledgeDocument).join(KnowledgeDocument)
                      .where(KnowledgeChunk.id.in_(list(fused)))).all()
    from app.modules.tie.policy import STOPWORDS
    q_terms = {t for t in tokens(query) if len(t) > 2 and t not in STOPWORDS} or {t for t in tokens(query) if len(t) > 1}
    hits = []
    for chunk, doc in rows:
        c_terms = set(tokens(chunk.folded))
        place_hit = bool(alias_tokens & c_terms)
        matched = {t for t in q_terms if t in c_terms or fold_for_search(transliterate(t)) in c_terms
                   or (t in place_terms and place_hit)}
        coverage = len(matched) / len(q_terms) if q_terms else 0.0
        boost = 0.01 if alias_dests and set(chunk.destination_ids or []) & set(alias_dests) else 0.0
        score = fused[chunk.id] * 30 + coverage + boost
        sig = {**signals[chunk.id], "coverage": round(coverage, 3), "alias_boost": bool(boost)}
        hits.append(Hit(chunk.id, doc.id, chunk.text, chunk.language, score, sig, doc_meta(doc)))
    hits.sort(key=lambda h: h.score, reverse=True)
    # Diversity: at most 3 chunks per document in the final context.
    per_doc: dict[uuid.UUID, int] = {}
    out = []
    for h in hits:
        if per_doc.get(h.document_id, 0) >= 3:
            continue
        per_doc[h.document_id] = per_doc.get(h.document_id, 0) + 1
        out.append(h)
        if len(out) >= k:
            break
    return out


def _or_query(folded: str) -> str:
    terms = [t for t in tokens(folded) if len(t) > 1][:24]
    safe = [t.replace("'", "") for t in terms if t.replace("'", "")]
    return " | ".join(f"'{t}'" for t in safe) or "''"


def doc_meta(doc: KnowledgeDocument) -> dict:
    return {"id": str(doc.id), "title": doc.title, "author": doc.author, "publisher": doc.publisher,
            "published_on": doc.published_on, "url": doc.url, "language": doc.original_language,
            "verification_status": doc.verification_status, "rights_status": doc.rights_status,
            "verified_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
            "classification": doc.access_classification, "is_synthetic": doc.is_synthetic,
            "revalidate_on": doc.revalidate_on.isoformat() if doc.revalidate_on else None}

