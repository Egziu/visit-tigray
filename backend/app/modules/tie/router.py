from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import AIMode
from app.core.db import get_db
from app.core.errors import AppError, not_found
from app.core.i18n import norm_locale
from app.core.security import rate_limit
from app.modules.audit import service as audit
from app.modules.identity.deps import optional_principal, require
from app.modules.identity.service import Principal
from app.modules.platform.service import get_setting, require_flag, set_setting
from app.modules.tie import evaluation, guide
from app.modules.tie.models import AIModel, Conversation, EvalRun, Feedback, Message
from app.modules.tie.policy import PERSONAS
from app.modules.tie.providers import get_chain

router = APIRouter(prefix="/api/tie", tags=["tie"])
admin_router = APIRouter(prefix="/api/bureau/ai", tags=["tie-admin"])

ALL_MODES = ["fully_local", "local_first_cloud_fallback", "cloud_assisted", "retrieval_only", "deterministic", "offline"]


@router.get("/status")
def status(db: Session = Depends(get_db)):
    pol = get_setting(db, "ai_policy")
    mode = guide.effective_mode(db)
    chain = get_chain(mode)
    first = next((p for p in chain if p.available(mode)), None)
    return {"mode": mode, "permitted_modes": pol.get("permitted_modes", []),
            "generative": first is not None,
            "provider": {"name": first.name, "model": first.model, "local": first.local, "available": True} if first else None,
            "configured_providers": [{"name": p.name, "model": p.model, "local": p.local} for p in chain],
            "notice": "Answers come only from approved, cited sources. Verify official information before travelling."}


@router.get("/personas")
def personas(locale: str = "en"):
    loc = norm_locale(locale)
    return [{"key": k, "name": v["name"].get(loc, v["name"]["en"]), "description": v["style"]} for k, v in PERSONAS.items()]


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=2000)
    locale: Literal["en", "ti", "am"] = "en"
    persona: str = Field(default="storyteller", max_length=30)
    conversation_id: uuid.UUID | None = None
    destination_slug: str | None = Field(default=None, max_length=100)


@router.post("/ask", dependencies=[Depends(rate_limit("ai"))])
def ask(body: AskIn, db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    require_flag(db, "ai_guide")
    ans = guide.ask(db, question=body.question, locale=body.locale, persona=body.persona, principal=p,
                    conversation_id=body.conversation_id, destination_slug=body.destination_slug)
    from app.modules.analytics.router import track
    track(db, "guide_question", destination_slug=body.destination_slug, locale=body.locale)
    db.commit()
    return ans.as_dict()


class FeedbackIn(BaseModel):
    message_id: uuid.UUID
    rating: Literal["up", "down"]
    comment: str | None = Field(default=None, max_length=1000)


@router.post("/feedback", status_code=201, dependencies=[Depends(rate_limit("write"))])
def feedback(body: FeedbackIn, db: Session = Depends(get_db)):
    m = db.get(Message, body.message_id)
    if m is None or m.role != "assistant":
        raise not_found("Message")
    db.add(Feedback(message_id=m.id, rating=body.rating, comment=body.comment))
    db.commit()
    return {"status": "recorded"}


@router.get("/conversations/{ident}")
def conversation(ident: uuid.UUID, db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    c = db.get(Conversation, ident)
    if c is None or (c.owner_id and (p is None or c.owner_id != p.id)):
        raise not_found("Conversation")
    msgs = db.execute(select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at)).scalars()
    return {"id": str(c.id), "persona": c.persona, "locale": c.locale,
            "messages": [{"id": str(m.id), "role": m.role, "content": m.content, "citations": m.citations,
                          "confidence": m.confidence} for m in msgs]}


# ---------------------------------------------------------------- administration

class PolicyIn(BaseModel):
    mode: AIMode
    permitted_modes: list[AIMode]
    max_tool_calls_per_turn: int = Field(default=3, ge=0, le=5)
    max_context_chunks: int = Field(default=8, ge=2, le=16)
    justification: str = Field(default="", max_length=1000)


@admin_router.get("/policy")
def get_policy(_=Depends(require("ai.admin")), db: Session = Depends(get_db)):
    return {**get_setting(db, "ai_policy"), "all_modes": ALL_MODES}


@admin_router.put("/policy")
def put_policy(body: PolicyIn, request: Request, p: Principal = Depends(require("ai.admin")), db: Session = Depends(get_db)):
    if body.mode not in body.permitted_modes:
        raise AppError(422, "mode_not_permitted", "The active mode must be one of the permitted modes.")
    external = {"cloud_assisted", "local_first_cloud_fallback"} & set(body.permitted_modes)
    if external and len(body.justification.strip()) < 30:
        raise AppError(422, "justification_required",
                       "Permitting cloud modes sends visitor questions to an external provider; record the approval/justification.")
    before = get_setting(db, "ai_policy")
    after = set_setting(db, "ai_policy", body.model_dump(exclude={"justification"}), actor_id=p.id)
    audit.record(db, action="ai.policy", resource_type="setting", resource_id="ai_policy", actor=p, request=request,
                 changes={"before": before, "after": after, "justification": body.justification})
    db.commit()
    return after


class ModelIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9][a-z0-9._:-]{1,79}$")
    role: Literal["chat", "embedding", "rerank", "stt", "tts", "ocr"]
    provider: Literal["ollama", "llamacpp", "vllm", "openai_compatible", "builtin"]
    base_url: str | None = Field(default=None, max_length=300)
    model_name: str = Field(max_length=200)
    version: str | None = None
    license: str | None = None
    commercial_use: Literal["yes", "restricted", "no", "unknown"] = "unknown"
    quantization: str | None = None
    profile: Literal["development", "regional_office", "datacenter"] = "development"
    enabled: bool = False
    notes: str | None = Field(default=None, max_length=4000)


def model_out(m: AIModel) -> dict:
    return {k: getattr(m, k) for k in ("key", "role", "provider", "base_url", "model_name", "version", "license",
                                       "commercial_use", "quantization", "profile", "enabled", "is_default",
                                       "eval_summary", "notes")}


@admin_router.get("/models")
def list_models(_=Depends(require("ai.admin")), db: Session = Depends(get_db)):
    return [model_out(m) for m in db.execute(select(AIModel).order_by(AIModel.role, AIModel.key)).scalars()]


@admin_router.post("/models", status_code=201)
def upsert_model(body: ModelIn, request: Request, p: Principal = Depends(require("ai.admin")), db: Session = Depends(get_db)):
    if body.enabled and body.commercial_use in ("no", "unknown"):
        raise AppError(422, "license_review_required", "Licence and commercial-use rights must be confirmed before enabling a model.")
    m = db.execute(select(AIModel).where(AIModel.key == body.key)).scalar_one_or_none() or AIModel(key=body.key)
    for k, v in body.model_dump().items():
        setattr(m, k, v)
    db.add(m)
    audit.record(db, action="ai.model_upsert", resource_type="ai_model", resource_id=body.key, actor=p, request=request,
                 changes={"enabled": body.enabled, "license": body.license})
    db.commit()
    return model_out(m)


@admin_router.post("/evaluations", status_code=201)
def run_eval(request: Request, mode: AIMode | None = None, p: Principal = Depends(require("ai.admin")),
             db: Session = Depends(get_db)):
    report = evaluation.run(db, evaluation.load(), mode)
    run = EvalRun(started_by=p.id, mode=report["mode"] or guide.effective_mode(db), dataset="evals/tie_eval.jsonl",
                  summary={k: v for k, v in report.items() if k != "results"}, results=report["results"],
                  pass_rate=report["pass_rate"])
    db.add(run)
    audit.record(db, action="ai.evaluation", resource_type="tie_eval", resource_id=str(run.id), actor=p, request=request,
                 changes={"pass_rate": report["pass_rate"]})
    db.commit()
    return {"id": str(run.id), **run.summary}


@admin_router.get("/evaluations")
def list_evals(_=Depends(require("ai.admin")), db: Session = Depends(get_db)):
    rows = db.execute(select(EvalRun).order_by(EvalRun.created_at.desc()).limit(20)).scalars()
    return [{"id": str(r.id), "created_at": r.created_at.isoformat(), "mode": r.mode, "pass_rate": r.pass_rate,
             "summary": r.summary} for r in rows]
