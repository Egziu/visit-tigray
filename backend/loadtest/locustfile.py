"""Baseline workload for public read paths and the deterministic planner.

Run: locust -f loadtest/locustfile.py --host http://127.0.0.1:8000 --headless -u 50 -r 10 -t 60s
The guide is exercised in retrieval-only mode (no model); model latency is benchmarked per
hardware profile separately (docs/AI_MODEL_EVALUATION.md).
"""
from __future__ import annotations

import random

from locust import HttpUser, between, task

SLUGS = ["aksum", "gheralta", "mekelle", "wukro", "yeha", "adwa"]


class Visitor(HttpUser):
    wait_time = between(0.5, 2.0)

    @task(5)
    def destinations(self):
        self.client.get("/api/destinations?locale=en", name="/api/destinations")

    @task(8)
    def destination(self):
        self.client.get(f"/api/destinations/{random.choice(SLUGS)}?locale=" + random.choice(["en", "ti", "am"]),  # noqa: S311
                        name="/api/destinations/{slug}")

    @task(2)
    def search(self):
        self.client.get("/api/destinations?q=" + random.choice(["aksum", "ኣክሱም", "church", "adwa"]),  # noqa: S311
                        name="/api/destinations?q")

    @task(2)
    def events(self):
        self.client.get("/api/events", name="/api/events")

    @task(1)
    def plan(self):
        self.client.post("/api/planner/plan", json={"days": 3, "interests": ["history"]}, name="/api/planner/plan")

    @task(1)
    def guide(self):
        self.client.post("/api/tie/ask", json={"question": "When was Aksum inscribed by UNESCO?", "locale": "en"},
                         name="/api/tie/ask (retrieval-only)")
