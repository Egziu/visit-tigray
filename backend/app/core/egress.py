"""Outbound network policy: the single choke point for every external HTTP call.

Why this exists
---------------
* **Data sovereignty**: in ``fully_local`` (and ``offline``/``retrieval_only``/``deterministic``)
  AI modes, no visitor conversation, knowledge document, embedding or analytics payload may leave
  the deployment. The guard rejects the request *before* a socket is opened.
* **SSRF prevention**: requests to cloud-metadata or link-local addresses are always refused, and
  hosts are never taken from user input without passing through ``check_url``.

Host classification is purely syntactic. A hostname that is neither an IP literal nor in the
configured local list counts as *external*, and no DNS lookup is made to decide (a lookup would
itself be egress and is spoofable).
"""
from __future__ import annotations

import ipaddress
import logging
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlsplit

import httpx

from app.core.config import get_settings

log = logging.getLogger("visit_tigray.egress")

Purpose = Literal["ai_inference", "embedding", "oidc", "notification", "integration", "scan"]
AI_PURPOSES = {"ai_inference", "embedding"}
LOCAL_ONLY_MODES = {"fully_local", "offline", "retrieval_only", "deterministic"}

_BLOCKED_NETS = [ipaddress.ip_network(n) for n in ("169.254.0.0/16", "fe80::/10", "0.0.0.0/8")]


class EgressBlocked(Exception):
    def __init__(self, url: str, reason: str):
        super().__init__(f"egress blocked to {url}: {reason}")
        self.url, self.reason = url, reason


@dataclass
class EgressDecision:
    allowed: bool
    host_class: Literal["local", "external", "forbidden"]
    reason: str


# In-process ledger so tests and /metrics can prove what was (not) attempted.
EGRESS_LEDGER: list[dict] = []


def classify_host(host: str) -> Literal["local", "external", "forbidden"]:
    host = (host or "").strip("[]").lower()
    if not host:
        return "forbidden"
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        if host == "localhost" or host.endswith(".localhost") or host in get_settings().local_ai_hosts:
            return "local"
        if host.endswith(".internal") or host.endswith(".local"):
            # Private DNS zones are only local when explicitly configured.
            return "local" if host in get_settings().local_ai_hosts else "external"
        return "external"
    if any(ip in n for n in _BLOCKED_NETS):
        return "forbidden"
    if ip.is_loopback or ip.is_private:
        return "local"
    return "external"


def decide(url: str, purpose: Purpose, ai_mode: str) -> EgressDecision:
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https"):
        return EgressDecision(False, "forbidden", f"scheme {parts.scheme!r} not allowed")
    host_class = classify_host(parts.hostname or "")
    if host_class == "forbidden":
        return EgressDecision(False, host_class, "link-local/metadata or empty host")
    if purpose in AI_PURPOSES and host_class == "external" and ai_mode in LOCAL_ONLY_MODES:
        return EgressDecision(False, host_class, f"AI mode {ai_mode} forbids external AI egress")
    if host_class == "external" and parts.scheme != "https":
        return EgressDecision(False, host_class, "external egress requires https")
    return EgressDecision(True, host_class, "ok")


def check_url(url: str, purpose: Purpose, ai_mode: str) -> None:
    d = decide(url, purpose, ai_mode)
    EGRESS_LEDGER.append({"url": url, "purpose": purpose, "mode": ai_mode, "allowed": d.allowed,
                          "host_class": d.host_class})
    if not d.allowed:
        log.warning("egress blocked purpose=%s mode=%s url=%s reason=%s", purpose, ai_mode, url, d.reason)
        raise EgressBlocked(url, d.reason)


class _GuardedTransport(httpx.HTTPTransport):
    def __init__(self, purpose: Purpose, ai_mode: str, **kw):
        super().__init__(**kw)
        self.purpose, self.ai_mode = purpose, ai_mode

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        check_url(str(request.url), self.purpose, self.ai_mode)  # re-checked on every hop/redirect
        return super().handle_request(request)


def guarded_client(purpose: Purpose, ai_mode: str, timeout: float = 30.0,
                   transport: httpx.BaseTransport | None = None) -> httpx.Client:
    """Return an httpx client whose every request passes the egress policy.

    ``transport`` lets tests inject a mock transport; the policy check still runs first.
    """
    if transport is None:
        transport = _GuardedTransport(purpose, ai_mode)
    else:
        inner = transport

        class _Wrapped(httpx.BaseTransport):
            def handle_request(self, request: httpx.Request) -> httpx.Response:
                check_url(str(request.url), purpose, ai_mode)
                return inner.handle_request(request)

        transport = _Wrapped()
    return httpx.Client(transport=transport, timeout=timeout, follow_redirects=False)
