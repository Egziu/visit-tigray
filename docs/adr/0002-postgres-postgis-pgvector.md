# ADR-0002: PostgreSQL with PostGIS, pgvector and pg_trgm as the single data platform

**Status:** accepted · 2026-11-12

**Decision.** Use PostgreSQL 16 for relational data, geography (PostGIS), vector retrieval (pgvector HNSW) and lexical search
(`tsvector` with the `simple` config + trigram) instead of separate OpenSearch or vector databases.

**Rationale.** One system to secure, back up and restore. Permission filters can be applied in the same SQL as vector ranking.
Volumes are expected to be modest (thousands of documents). Tigrinya/Amharic have no PostgreSQL stemmers, so search relies on
application-side folding and transliteration, which work identically for every index type.

**Revisit when** corpus size or query load makes HNSW recall/latency or FTS ranking insufficient (measure first). OpenSearch is the
evaluated alternative.
