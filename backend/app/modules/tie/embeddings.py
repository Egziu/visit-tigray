"""Embedding providers.

* ``hashing`` (default, dependency-free): signed feature hashing of folded character n-grams and
  words, plus their Latin transliteration. It is a **lexical baseline, not a semantic model**: it
  matches spelling variants and cross-script names (Aksum/አክሱም) but not paraphrases or
  translations. It exists so the platform works fully offline with zero model downloads, and so
  tests are deterministic.
* ``ollama``: any embedding model served by a local Ollama (e.g. ``bge-m3``,
  ``nomic-embed-text``). Configure ``EMBEDDING_MODEL`` and keep ``EMBEDDING_DIM`` consistent with
  the ``knowledge_chunks.embedding`` column (re-index after changing).
* ``openai_compatible``: a local text-embeddings-inference / llama.cpp ``/v1/embeddings`` server.

Every network provider goes through the egress guard with purpose ``embedding``.
"""
from __future__ import annotations

import hashlib
import math
import re
from functools import lru_cache

from app.core.config import get_settings
from app.core.egress import guarded_client
from app.core.ethiopic import fold_for_search, transliterate

DIM = 384


class HashingEmbedder:
    name = "hashing-ngram-v1"
    local = True

    def __init__(self, dim: int = DIM):
        self.dim = dim

    def _features(self, text: str) -> list[str]:
        base = fold_for_search(text)
        latin = fold_for_search(transliterate(text))
        feats: list[str] = []
        for variant in {base, latin}:
            words = re.findall(r"[\wሀ-፿]+", variant)
            feats += [f"w:{w}" for w in words if len(w) > 1]
            for w in words:
                padded = f" {w} "
                for n in (3, 4):
                    feats += [f"c{n}:{padded[i:i + n]}" for i in range(max(0, len(padded) - n + 1))]
        return feats

    def embed(self, texts: list[str], mode: str = "fully_local") -> list[list[float]]:
        out = []
        for t in texts:
            v = [0.0] * self.dim
            for f in self._features(t):
                h = int.from_bytes(hashlib.blake2b(f.encode(), digest_size=8).digest(), "big")
                v[h % self.dim] += 1.0 if (h >> 63) & 1 else -1.0
            norm = math.sqrt(sum(x * x for x in v)) or 1.0
            out.append([x / norm for x in v])
        return out


class OllamaEmbedder:
    local = True

    def __init__(self, base_url: str, model: str):
        self.base_url, self.model, self.name = base_url.rstrip("/"), model, f"ollama:{model}"

    def embed(self, texts: list[str], mode: str = "fully_local") -> list[list[float]]:
        with guarded_client("embedding", mode, timeout=get_settings().ai_timeout_seconds) as c:
            r = c.post(f"{self.base_url}/api/embed", json={"model": self.model, "input": texts})
            r.raise_for_status()
            vecs = r.json()["embeddings"]
        if vecs and len(vecs[0]) != DIM:
            raise ValueError(f"embedding dim {len(vecs[0])} != column dim {DIM}; re-index required")
        return vecs


class OpenAICompatEmbedder:
    def __init__(self, base_url: str, model: str):
        self.base_url, self.model, self.name = base_url.rstrip("/"), model, f"oai:{model}"

    def embed(self, texts: list[str], mode: str = "fully_local") -> list[list[float]]:
        with guarded_client("embedding", mode, timeout=get_settings().ai_timeout_seconds) as c:
            r = c.post(f"{self.base_url}/v1/embeddings", json={"model": self.model, "input": texts})
            r.raise_for_status()
            return [d["embedding"] for d in r.json()["data"]]


@lru_cache
def get_embedder():
    s = get_settings()
    if s.embedding_provider == "ollama":
        return OllamaEmbedder(s.ollama_base_url, s.embedding_model)
    return HashingEmbedder(DIM)
