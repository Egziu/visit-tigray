"""Chat model providers behind one interface. All network calls go through the egress guard.

``local`` is not taken from configuration labels: it is derived from the endpoint host by the
same classifier the egress guard uses, so a cloud endpoint can never be reported as local.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx
from prometheus_client import Histogram

from app.core.config import get_settings
from app.core.egress import EgressBlocked, classify_host, guarded_client

AI_LATENCY = Histogram("vt_ai_inference_seconds", "Chat inference latency", ["provider", "mode", "outcome"],
                       buckets=(0.25, 0.5, 1, 2, 4, 8, 15, 30, 60, 120))


class ProviderError(Exception):
    pass


@dataclass
class ChatResult:
    text: str
    provider: str
    model: str
    local: bool
    latency_ms: int


class ChatProvider:
    name = "base"
    model = ""
    base_url = ""
    transport: httpx.BaseTransport | None = None  # tests inject a mock transport

    @property
    def local(self) -> bool:
        return classify_host(urlsplit(self.base_url).hostname or "") == "local"

    def chat(self, messages: list[dict], *, mode: str, json_mode: bool = True, max_tokens: int = 700) -> ChatResult:
        raise NotImplementedError

    def _client(self, mode: str):
        return guarded_client("ai_inference", mode, timeout=get_settings().ai_timeout_seconds, transport=self.transport)


class OllamaProvider(ChatProvider):
    name = "ollama"

    def __init__(self, base_url: str, model: str):
        self.base_url, self.model = base_url.rstrip("/"), model

    def chat(self, messages, *, mode, json_mode=True, max_tokens=700) -> ChatResult:
        t0 = time.perf_counter()
        body = {"model": self.model, "messages": messages, "stream": False,
                "options": {"temperature": 0.2, "num_predict": max_tokens}}
        if json_mode:
            body["format"] = "json"
        try:
            with self._client(mode) as c:
                r = c.post(f"{self.base_url}/api/chat", json=body)
                r.raise_for_status()
                text = r.json()["message"]["content"]
        except EgressBlocked:
            raise
        except (httpx.HTTPError, KeyError, ValueError) as exc:
            AI_LATENCY.labels(self.name, mode, "error").observe(time.perf_counter() - t0)
            raise ProviderError(f"ollama: {exc}") from exc
        elapsed = time.perf_counter() - t0
        AI_LATENCY.labels(self.name, mode, "ok").observe(elapsed)
        return ChatResult(text, self.name, self.model, self.local, int(elapsed * 1000))


class OpenAICompatibleProvider(ChatProvider):
    """llama.cpp server, vLLM, or (cloud-assisted modes only) a hosted OpenAI-compatible API."""

    def __init__(self, name: str, base_url: str, model: str, api_key: str | None = None):
        self.name, self.base_url, self.model, self.api_key = name, base_url.rstrip("/"), model, api_key

    def chat(self, messages, *, mode, json_mode=True, max_tokens=700) -> ChatResult:
        t0 = time.perf_counter()
        body = {"model": self.model, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        try:
            with self._client(mode) as c:
                r = c.post(f"{self.base_url}/v1/chat/completions", json=body, headers=headers)
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"]
        except EgressBlocked:
            raise
        except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
            AI_LATENCY.labels(self.name, mode, "error").observe(time.perf_counter() - t0)
            raise ProviderError(f"{self.name}: {exc}") from exc
        elapsed = time.perf_counter() - t0
        AI_LATENCY.labels(self.name, mode, "ok").observe(elapsed)
        return ChatResult(text, self.name, self.model, self.local, int(elapsed * 1000))


def local_providers() -> list[ChatProvider]:
    s = get_settings()
    out: list[ChatProvider] = []
    if s.vllm_base_url:
        out.append(OpenAICompatibleProvider("vllm", s.vllm_base_url, s.local_chat_model))
    if s.llamacpp_base_url:
        out.append(OpenAICompatibleProvider("llamacpp", s.llamacpp_base_url, s.local_chat_model))
    out.append(OllamaProvider(s.ollama_base_url, s.local_chat_model))
    return [p for p in out if p.local]  # misconfigured "local" endpoints on public hosts are dropped


def cloud_provider() -> ChatProvider | None:
    s = get_settings()
    if s.cloud_ai_base_url and s.cloud_ai_model:
        return OpenAICompatibleProvider("cloud", s.cloud_ai_base_url, s.cloud_ai_model, s.cloud_ai_api_key)
    return None


def provider_chain(mode: str) -> list[ChatProvider]:
    """Ordered providers permitted in ``mode``. Non-generative modes return an empty chain."""
    if mode == "fully_local":
        return local_providers()
    cloud = cloud_provider()
    if mode == "local_first_cloud_fallback":
        return local_providers() + ([cloud] if cloud else [])
    if mode == "cloud_assisted":
        return ([cloud] if cloud else []) + local_providers()
    return []  # retrieval_only | deterministic | offline


# Test hook: tests may replace the chain (e.g. with a fake or a deliberately external provider).
# The override bypasses the chain builder's filtering but NOT the egress guard, which is the point:
# tests prove the guard alone blocks external inference in local-only modes.
_override: list[ChatProvider] | None = None

GENERATIVE_MODES = {"fully_local", "local_first_cloud_fallback", "cloud_assisted"}


def get_chain(mode: str) -> list[ChatProvider]:
    if mode not in GENERATIVE_MODES:
        return []
    return list(_override) if _override is not None else provider_chain(mode)
