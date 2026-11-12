# ADR-0005: The itinerary planner is deterministic; AI only explains

**Status:** accepted · 2026-11-12

**Decision.** Feasibility (stops, order, time budgets, advisories, accessibility) is computed by rule-based code over verified
data. Distances without a verified segment are labelled straight-line, and travel time is unknown. Language models may describe a
plan (via the read-only `plan_itinerary` tool) but cannot alter it.

**Consequences.** Plans are reproducible, explainable and safe under official advisories. Quality depends on verified route
segments and destination facts entered by staff.
