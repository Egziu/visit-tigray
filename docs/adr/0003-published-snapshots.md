# ADR-0003: Working copy + immutable published snapshot for CMS content

**Status:** accepted · 2026-11-12

**Decision.** Staff edit a working copy. Publishing writes an immutable JSON snapshot (served publicly) and a numbered revision
holding both snapshot and working copy. Rollback republishes a revision's working copy.

**Consequences.** Drafts can never leak through public queries. The live page stays visible while edits are pending (a bug found
in testing and fixed). Search and geo use derived columns refreshed on publish.
