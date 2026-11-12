"""Allowlisted, typed tool gateway for TIE.

* Only the tools registered here exist. There is no SQL, shell, HTTP or admin tool.
* Arguments are validated with Pydantic; unknown arguments are rejected.
* Every tool runs with the *calling user's* principal, so permissions are enforced by the same
  server-side code that serves the public API. The model cannot escalate.
* The per-turn call budget is enforced by the caller (guide.ask) from the admin AI policy.
* Tools are read-only. Nothing the AI can call publishes, edits or approves anything.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.i18n import norm_locale


class _Args(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SearchArgs(_Args):
    query: str = Field(min_length=2, max_length=300)


class DestinationArgs(_Args):
    slug: str = Field(pattern=r"^[a-z0-9-]{2,100}$")


class NoArgs(_Args):
    pass


class PlanArgs(_Args):
    days: int = Field(ge=1, le=7)
    interests: list[str] = Field(default_factory=list, max_length=6)


@dataclass
class Tool:
    name: str
    description: str
    args: type[_Args]
    fn: Callable


class ToolError(Exception):
    pass


def _search(db: Session, principal, locale: str, args: SearchArgs) -> dict:
    from app.modules.knowledge.retrieval import retrieve
    hits = retrieve(db, args.query, principal=principal, k=4)
    return {"hits": hits}  # Hit objects: guide.ask renumbers them into the citation list


def _destination(db: Session, principal, locale: str, args: DestinationArgs) -> dict:
    from app.modules.content.models import Destination
    from app.modules.content.service import localize_snapshot
    d = db.execute(select(Destination).where(Destination.slug == args.slug)).scalar_one_or_none()
    if d is None or not d.published_snapshot:
        return {"error": "not found"}
    s = localize_snapshot(d.published_snapshot, locale)
    keep = ("name", "summary", "area", "visit_duration_minutes", "permit_required", "permit_authority", "accessibility",
            "etiquette", "verified_at", "is_stale")
    return {k: s.get(k) for k in keep}


def _advisories(db: Session, principal, locale: str, args: NoArgs) -> dict:
    from app.modules.content.service import active_advisories, advisory_out
    return {"advisories": [advisory_out(a, locale) for a in active_advisories(db)]}


def _plan(db: Session, principal, locale: str, args: PlanArgs) -> dict:
    from app.modules.planner.engine import PlanRequest, build_plan
    plan = build_plan(db, PlanRequest(days=args.days, interests=args.interests, locale=locale))
    return {"mode": plan["mode"], "days": [[s["name"] for s in d["stops"]] for d in plan["days"]],
            "notice": plan["notice"]}


TOOLS: dict[str, Tool] = {t.name: t for t in [
    Tool("search_knowledge", "search_knowledge(query): search approved knowledge for more documents", SearchArgs, _search),
    Tool("get_destination", "get_destination(slug): published facts for one destination", DestinationArgs, _destination),
    Tool("list_advisories", "list_advisories(): current official travel advisories", NoArgs, _advisories),
    Tool("plan_itinerary", "plan_itinerary(days, interests): deterministic itinerary outline", PlanArgs, _plan),
]}


def tools_doc() -> str:
    return "\n".join(f"- {t.description}" for t in TOOLS.values())


def execute(db: Session, principal, locale: str, name: str, raw_args) -> dict:
    tool = TOOLS.get(name)
    if tool is None:
        raise ToolError(f"unknown tool {name!r}")
    try:
        args = tool.args.model_validate(raw_args or {})
    except ValidationError as exc:
        raise ToolError(f"invalid arguments for {name}: {exc.errors()[:2]}") from exc
    return tool.fn(db, principal, norm_locale(locale), args)
