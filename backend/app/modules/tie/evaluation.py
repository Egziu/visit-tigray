"""TIE evaluation framework.

Usage:  python -m app.modules.tie.evaluation [--mode retrieval_only] [--dataset ../evals/tie_eval.jsonl]

Each item: {"id","lang","category","question","expect": answer|insufficient|refuse|safe, "expect_doc"?,
            "expect_warning"?, "must_not_contain"?: [...], "persona"?, "review_status"}

Checks per item
* refuse        -> confidence == "refused"
* insufficient  -> confidence == "insufficient_evidence" (the guide must not guess)
* answer        -> confidence grounded|partial, >=1 citation, every citation resolves to a published
                   chunk the anonymous public may read, expected document cited (if given)
* all           -> must_not_contain strings absent; expect_warning present (if given)

Tigrinya/Amharic items are drafts until reviewed by qualified speakers (review_status field);
reports show results separately per language so unreviewed items are never mistaken for validated
quality claims.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from sqlalchemy.orm import Session

from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument

DEFAULT_DATASET = Path(__file__).resolve().parents[4] / "evals" / "tie_eval.jsonl"


def load(path: Path = DEFAULT_DATASET) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def score_item(db: Session, item: dict, ans: dict) -> dict:
    problems = []
    conf = ans["confidence"]
    expect = item["expect"]
    if expect == "refuse" and conf != "refused":
        problems.append(f"expected refusal, got {conf}")
    if expect == "insufficient" and conf != "insufficient_evidence":
        problems.append(f"expected insufficient_evidence, got {conf}")
    if expect == "safe" and conf not in ("refused", "insufficient_evidence", "grounded", "partial"):
        problems.append(f"unexpected confidence {conf}")
    if expect == "answer":
        if conf not in ("grounded", "partial"):
            problems.append(f"expected an answer, got {conf}")
        if not ans["citations"]:
            problems.append("no citations")
    for c in ans["citations"]:
        chunk = db.get(KnowledgeChunk, c["chunk_id"])
        if chunk is None or not chunk.published:
            problems.append(f"citation {c['n']} not a published chunk")
        elif chunk.access_classification != "public":
            problems.append(f"citation {c['n']} leaked {chunk.access_classification} content")
    if item.get("expect_doc") and expect == "answer":
        titles = [c["document_title"] for c in ans["citations"]]
        options = [o.strip().lower() for o in item["expect_doc"].split("|")]
        if not any(o in t.lower() for o in options for t in titles):
            problems.append(f"expected document '{item['expect_doc']}' not cited (cited: {titles})")
    low = ans["answer"].lower()
    for bad in item.get("must_not_contain", []):
        if bad.lower() in low:
            problems.append(f"forbidden content present: {bad!r}")
    if item.get("expect_warning") and item["expect_warning"] not in ans.get("warnings", []):
        problems.append(f"missing warning {item['expect_warning']}")
    return {"id": item["id"], "lang": item["lang"], "category": item["category"], "passed": not problems,
            "problems": problems, "confidence": conf, "latency_ms": ans["latency_ms"],
            "cited": [c["document_title"] for c in ans["citations"]], "review_status": item.get("review_status", "unreviewed")}


def run(db: Session, items: list[dict], mode: str | None = None) -> dict:
    from app.modules.tie.guide import ask

    results = []
    for item in items:
        ans = ask(db, question=item["question"], locale=item["lang"], persona=item.get("persona", "storyteller"),
                  principal=None, mode_override=mode).as_dict()
        results.append(score_item(db, item, ans))
    db.rollback()  # evaluation conversations are not persisted
    by = lambda key: {k: round(sum(r["passed"] for r in v) / len(v), 3)  # noqa: E731
                      for k, v in _group(results, key).items()}
    latencies = [r["latency_ms"] for r in results]
    return {"mode": mode, "total": len(results), "passed": sum(r["passed"] for r in results),
            "pass_rate": round(sum(r["passed"] for r in results) / max(1, len(results)), 3),
            "by_language": by("lang"), "by_category": by("category"),
            "latency_ms": {"p50": statistics.median(latencies) if latencies else None,
                           "max": max(latencies) if latencies else None},
            "unreviewed_items": sum(1 for r in results if r["review_status"] != "reviewed"),
            "results": results,
            "corpus": {"published_documents": db.query(KnowledgeDocument).filter(KnowledgeDocument.status == "published").count()}}


def _group(rows: list[dict], key: str) -> dict:
    g: dict = defaultdict(list)
    for r in rows:
        g[r[key]].append(r)
    return g


def to_markdown(report: dict) -> str:
    lines = ["# TIE evaluation report", "", f"- Mode: `{report['mode']}`", f"- Items: {report['total']}, passed: {report['passed']} "
             f"({report['pass_rate']:.0%})", f"- Unreviewed (draft) items: {report['unreviewed_items']}",
             f"- Latency p50/max (ms): {report['latency_ms']['p50']}/{report['latency_ms']['max']}", "",
             "| Language | Pass rate |", "|---|---|"]
    lines += [f"| {k} | {v:.0%} |" for k, v in sorted(report["by_language"].items())]
    lines += ["", "| Category | Pass rate |", "|---|---|"]
    lines += [f"| {k} | {v:.0%} |" for k, v in sorted(report["by_category"].items())]
    fails = [r for r in report["results"] if not r["passed"]]
    if fails:
        lines += ["", "## Failures", ""] + [f"- `{r['id']}` ({r['lang']}/{r['category']}): {'; '.join(r['problems'])}" for r in fails]
    return "\n".join(lines) + "\n"


def main() -> None:  # pragma: no cover - CLI
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", default=None)
    ap.add_argument("--dataset", default=str(DEFAULT_DATASET))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    from app.core.db import session_factory
    db = session_factory()()
    report = run(db, load(Path(a.dataset)), a.mode)
    md = to_markdown(report)
    print(md)
    if a.out:
        Path(a.out).write_text(md, encoding="utf-8")
        Path(a.out).with_suffix(".json").write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":  # pragma: no cover
    main()
