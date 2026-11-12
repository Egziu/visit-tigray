# ADR-0006: A dependency-free hashing embedder as the default baseline

**Status:** accepted · 2026-11-12

**Context.** Model weights were unreachable from the build environment, and many deployments will start offline.

**Decision.** Default to a deterministic feature-hashing embedder (character n-grams + words + transliteration, 384-d), clearly
documented as a lexical baseline. Semantic embedding models plug in via `EMBEDDING_PROVIDER` after evaluation.

**Consequences.** Works offline and in CI. Measured weakness: cross-lingual retrieval for non-place concepts (2–3 eval failures).
Upgrading to a multilingual model is the top AI quality item on the roadmap.
