# Roadmap

Status key: ✅ done in this branch · 🟡 partial · ⛔ blocked on external input · ⏳ planned

## Delivered (this branch)

✅ Phase 0 baseline, audit, backlog · ✅ modular backend, migrations, identity/MFA/OIDC, RBAC, audit · ✅ destination CMS, media
pipeline, advisories, events, Ethiopian calendar · ✅ Knowledge Vault, TIE with modes, egress guard, evaluation framework ·
✅ deterministic planner and exports · ✅ Tigray Memories with moderation, appeals, export/delete · ✅ provider directory with
verification · ✅ governed awards · ✅ analytics with provenance · ✅ Bureau assistant · ✅ CI, compose, least privilege, backups,
load-test baseline · 🟡 Next.js public site, Bureau console, PWA (see `docs/FRONTEND.md`).

## Next (engineering, can start immediately)

1. ⏳ Editorial workflow tables: task assignment, editorial calendar, comment threads on drafts (`editorial.assign` exists).
2. ⏳ S3/MinIO storage backend with server-side encryption and signed URLs; resumable uploads (tus).
3. ⏳ Knowledge freshness report; OCR integration (Tesseract `tir`/`amh`) after a quality evaluation.
4. ⏳ Cross-encoder reranker and a multilingual embedding model behind the registry (requires the evaluation in `docs/AI_MODEL_EVALUATION.md`).
5. ⏳ Festival/concept aliases (not just places) to close the cross-lingual retrieval gap found in evaluation.
6. ⏳ WebAuthn/passkeys for staff; CAPTCHA/bot challenge on registration.
7. ⏳ OpenTelemetry tracing exporter; Prometheus alert rules.
8. ⏳ Edge ↔ central content synchronization for institutional offline servers.
9. ⏳ Immersive heritage: virtual exhibitions, timelines UI, 360° and 3D viewers for approved media only, with reconstruction labels.
10. ⏳ Voice: STT/TTS evaluation for Tigrinya; professional narration for audio guides.

## Blocked on institutional input ⛔

* Bureau authorization, branding approval and an official domain.
* Licensed photography and rights register; verified destination facts, contacts, hours and permits.
* Native-speaker review of the Tigrinya/Amharic UI, glossary and evaluation set.
* Legal review: privacy notice, competition rules, prize funding, age policy, data retention.
* Model selection after measured evaluation on Bureau hardware; GPU procurement for the office profile.
* Integration agreements (Visit Ethiopia, ministries) before any data exchange.
