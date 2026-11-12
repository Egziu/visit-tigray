# Local AI Architecture — Tigray Intelligence Engine (TIE)

TIE is the platform's AI subsystem. Its design premise is that **useful, honest answers must not depend on an external AI
provider**. Generation is optional. Retrieval, permission filtering, citation and planning are deterministic code that keeps
working when no model is available.

## 1. Components (all in `backend/app/modules/tie` and `…/knowledge`)

| # | Component | Implementation | Status |
|---|---|---|---|
| 1 | Model provider abstraction | `providers.py`: `ChatProvider` with Ollama, OpenAI-compatible (llama.cpp server, vLLM, cloud) | done |
| 2 | Local inference gateway | `providers.local_providers()` + **egress guard**; `local` derived from the endpoint host | done |
| 3 | Embedding service | `embeddings.py`: hashing baseline (default), Ollama, OpenAI-compatible | done (semantic models not benchmarked here) |
| 4 | Knowledge ingestion | `knowledge/ingestion.py`: scan, extract, detect language, screen for injection, chunk, embed | done |
| 5 | Document processing / OCR | txt/md/html/pdf text layer done; **OCR unresolved** (scanned PDFs are rejected with `ocr_required`) | partial |
| 6 | Multilingual retrieval | Ethiopic folding, transliteration, alias expansion, cross-script names | done (lexical) |
| 7 | Vector + lexical search | pgvector HNSW + `tsvector` + trigram, RRF fusion | done |
| 8 | Geographic retrieval | destination filters + `ST_DWithin` radius filter | done |
| 9 | Reranking | coverage reranker (alias-aware); cross-encoder is a plug-in point | done / planned |
| 10 | Context construction | `context.py`: numbered, delimited, neutralized documents; rules in system prompt | done |
| 11 | Citation & provenance validation | `policy.validate_output`: invalid citations removed, uncited answers downgraded, unsupported operational claims flagged | done |
| 12 | Conversation management | `tie_conversations/messages`, ownership, 30-day expiry | done |
| 13 | Tool execution gateway | `tools.py`: allowlisted, typed, read-only, caller's permissions, per-turn budget | done |
| 14 | Policy & safety engine | `policy.py`: en/ti/am refusals, injection detection + stripping, operational-intent guard | done |
| 15 | Evaluation framework | `evaluation.py` + `evals/tie_eval.jsonl` (34 items, en/ti/am) | done |
| 16 | Model registry & administration | `ai_models` table + `/api/bureau/ai/models` (licence gate) | done |
| 17 | Performance monitoring | `vt_ai_inference_seconds`, `vt_tie_answers_total`, latency in analytics | done |
| 18 | Feedback loop | `/api/tie/feedback`, assistant FAQ/feedback summaries, eval runs stored | done |

## 2. Request flow

```mermaid
sequenceDiagram
  participant U as Visitor
  participant G as guide.ask
  participant P as policy
  participant R as retrieval (SQL)
  participant M as Model provider
  participant T as Tool gateway
  U->>G: question, locale, persona
  G->>P: screen_input
  alt circumvention / protected location / personal data
    P-->>U: refusal (localized), no retrieval
  end
  G->>R: retrieve(question minus injection sentences, principal)
  Note over R: classification filter IN SQL;<br/>vector + FTS + trigram → RRF → coverage rerank
  alt no evidence, or operational question without operational facts
    G-->>U: insufficient_evidence (never a guess)
  end
  alt AI mode allows generation and a provider is reachable
    G->>M: system rules + numbered untrusted documents
    opt tool call (≤ budget)
      M->>T: {"tool": "...", "args": {...}}
      T-->>M: read-only result (caller's permissions)
    end
    M-->>G: JSON answer + citations
    G->>P: validate_output (citations ⊆ context, claim guard)
  else retrieval_only / deterministic / offline / provider failed / egress blocked
    G->>G: extractive answer from top excerpts with [n] citations
  end
  G-->>U: answer · confidence · citations · warnings · provider{local}
```

## 3. Operating modes (administrator-controlled)

`PUT /api/bureau/ai/policy` (permission `ai.admin`, audited) sets the active mode and the **permitted** set. Permitting a cloud mode
requires a written justification.

| Mode | Generation | External egress for AI | Behaviour |
|---|---|---|---|
| `fully_local` (default) | local providers only | **blocked** | local model, extractive fallback |
| `local_first_cloud_fallback` | local → cloud | allowed (https only) | cloud used only if local fails |
| `cloud_assisted` | cloud → local | allowed | |
| `retrieval_only` | none | blocked | extractive cited answers |
| `deterministic` | none | blocked | same as retrieval-only. The planner is always deterministic |
| `offline` | none | blocked | intended for edge servers without uplink |

**Enforcement is not a label.** `app/core/egress.py` classifies hosts syntactically (loopback, RFC1918 and configured local
service names are local; anything else is external; link-local and metadata addresses are always forbidden). It checks every
request, including redirects, before the socket opens. The test `test_fully_local_blocks_external_egress_before_any_socket` patches
`socket.create_connection` and proves that an external provider in `fully_local` mode makes **zero** connection attempts. The
guide then falls back to cited extractive answers.

## 4. Hardware deployment profiles

No throughput figures are promised: none could be measured in the build environment (no GPU, no reachable model weights).
Measure with `scripts/` and the evaluation CLI on the target hardware before committing to capacity.

| Profile | Suggested hardware | Inference | Models (to be evaluated) | Notes |
|---|---|---|---|---|
| **Development** | 4–8 vCPU, 16 GB RAM, no GPU | Ollama on CPU, q4 quantization | 1.5B–3B instruct; or retrieval-only | Default dev mode is retrieval-only with hashing embeddings, so no downloads are needed |
| **Regional office** | 1 GPU with 16–24 GB VRAM, 64 GB RAM, NVMe | Ollama or llama.cpp server, 1–2 parallel slots | 7B–14B instruct at q4_K_M or q8; a multilingual embedding model (384-dim to match the schema, or migrate) | UPS + local backups; edge mode during uplink outages |
| **Regional data centre** | 2+ GPUs (≥ 40 GB each), redundant nodes | vLLM (continuous batching), OpenAI-compatible endpoint behind the egress guard | routed: small model for classification, larger for answers | HA PostgreSQL, Prometheus alerting on `vt_ai_inference_seconds` |

Configure via `.env`: `OLLAMA_BASE_URL`, `LLAMACPP_BASE_URL`, `VLLM_BASE_URL`, `LOCAL_CHAT_MODEL`, `EMBEDDING_PROVIDER`,
`EMBEDDING_MODEL`. Pull weights with `docker compose --profile ai exec ollama ollama pull <model>`. Weights live in the `ollama`
volume or an authorized model store, **never in git**.

## 5. Security of the AI subsystem

| Threat | Control |
|---|---|
| Prompt injection (direct) | pattern detection (en/ti/am), injected sentences stripped from the retrieval query, rules live in the system prompt, output validated |
| Indirect injection (documents) | ingestion screening flags instruction-like text; approval blocked until a reviewer acknowledges it; retrieved text neutralized and delimited as untrusted data |
| Knowledge-base poisoning | four-eyes approval, rights/provenance metadata, custodian approval for restricted/sacred, versioning, withdraw |
| Unauthorized retrieval / cross-user leakage | classification filter in SQL; conversations owned and expiring; canary test (`VAULT-CANARY-7731`) |
| Tool-call manipulation | allowlist, Pydantic `extra="forbid"`, read-only tools, caller's permissions, call budget |
| Endpoint abuse / resource exhaustion | rate limits (`RATE_LIMIT_AI`), question length limits, context/tool budgets, timeouts |
| Sensitive disclosure | protected-location refusals, coordinate coarsening, no personal data in tools |
| Unsafe automated actions | no write tools exist; the Bureau assistant has no write path |
| Data exfiltration to cloud | egress guard + mode policy + audited justification |

## 6. Speech, vision, OCR (multimodal) — unresolved

Interfaces are **not** implemented in this branch. Requirements and candidates for evaluation:

* **Speech-to-text:** candidates include Whisper-family models (Amharic support is documented; Tigrinya support is not, as far as
  known — verify) and Meta MMS (covers Tigrinya and Amharic, but its licence is reported as **non-commercial**, so licence review is
  required). Accuracy must be measured on Tigrinya speech recorded with consent.
* **Text-to-speech:** use professional narration for audio guides until a synthetic voice passes native-speaker review.
* **OCR:** Tesseract publishes `tir` and `amh` traineddata. Integrate behind `ingestion.extract_text` once quality has been measured
  on real archival scans.
* **Image interpretation:** must express uncertainty and must never identify private individuals. Not started.
