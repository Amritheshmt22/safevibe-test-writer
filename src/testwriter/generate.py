"""LLM backends for test generation.

Three interchangeable backends, all free:

- OllamaBackend: local open-weight models via Ollama (the SafeVibe plan's
  default; zero inference budget, pinned weights = reproducible).
- OpenAICompatibleBackend: any free hosted tier that speaks the OpenAI
  chat-completions API (OpenRouter free models, Gemini free tier,
  GitHub Models). Configured entirely through environment variables:
  TESTWRITER_LLM_BASE_URL, TESTWRITER_LLM_API_KEY, TESTWRITER_LLM_MODEL.
- ScriptedBackend: replays raw LLM completions recorded in a directory
  (one file per round, ``round-<n>.txt`` for the iterative arm and
  ``baseline.txt`` for the one-shot arm). This is what makes the
  published experiment bundle exactly reproducible: the recorded
  completions in experiments/e2_test_backfill/llm_outputs/ are the
  model outputs, verbatim.

Raw completions are stored unmodified; the test file is extracted from
the first ```python fenced block (or the whole reply if unfenced).
"""
from __future__ import annotations

import ast
import json
import os
import re
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass
class GenerationResult:
    raw: str
    code: str | None  # extracted test code, None if extraction/parsing failed
    error: str | None = None


_CODE_BLOCK_RE = re.compile(r"```(?:python|py)\s*\n(.*?)```", re.S)


def extract_code(raw: str) -> GenerationResult:
    """Pull the test code out of a raw LLM completion and syntax-check it."""
    blocks = _CODE_BLOCK_RE.findall(raw)
    code = "\n\n".join(blocks).strip() if blocks else raw.strip()
    if not code:
        return GenerationResult(raw=raw, code=None, error="empty completion")
    try:
        ast.parse(code)
    except SyntaxError as exc:
        return GenerationResult(raw=raw, code=None,
                                error=f"generated code does not parse: {exc}")
    return GenerationResult(raw=raw, code=code)


class Backend:
    name = "base"

    def complete(self, prompt: str, system: str) -> str:
        raise NotImplementedError


class OllamaBackend(Backend):
    """Local open-weight model through Ollama's HTTP API."""

    name = "ollama"

    def __init__(self, model: str = "qwen2.5-coder:7b",
                 host: str = "http://localhost:11434") -> None:
        self.model = model
        self.host = host.rstrip("/")

    def complete(self, prompt: str, system: str) -> str:
        body = json.dumps({
            "model": self.model,
            "prompt": f"{system}\n\n{prompt}",
            "stream": False,
            "options": {"temperature": 0.2, "seed": 42},
        }).encode()
        req = urllib.request.Request(f"{self.host}/api/generate", data=body,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            return json.loads(resp.read())["response"]


class OpenAICompatibleBackend(Backend):
    """Free hosted tiers behind the OpenAI chat-completions API.

    Works with OpenRouter (https://openrouter.ai/api/v1), Google Gemini's
    OpenAI-compatible endpoint, and GitHub Models. The key is read from
    the environment, never stored.
    """

    name = "openai-compatible"

    def __init__(self) -> None:
        self.base_url = os.environ.get("TESTWRITER_LLM_BASE_URL", "").rstrip("/")
        self.api_key = os.environ.get("TESTWRITER_LLM_API_KEY", "")
        self.model = os.environ.get("TESTWRITER_LLM_MODEL", "")
        if not (self.base_url and self.api_key and self.model):
            raise RuntimeError(
                "set TESTWRITER_LLM_BASE_URL, TESTWRITER_LLM_API_KEY and "
                "TESTWRITER_LLM_MODEL to use the hosted backend")

    def complete(self, prompt: str, system: str) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": prompt}],
            "temperature": 0.2,
            "seed": 42,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Content-Type": "application/json",
                     "Authorization": f"Bearer {self.api_key}"})
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read())
        return data["choices"][0]["message"]["content"]


class ScriptedBackend(Backend):
    """Replays recorded raw completions from a directory.

    Used for the published experiment bundle: prompts and raw outputs
    are pinned artifacts, so anyone can rerun the exact pipeline stages
    that follow generation.
    """

    name = "scripted"

    def __init__(self, directory: Path | str) -> None:
        self.directory = Path(directory)

    def load(self, filename: str) -> str:
        path = self.directory / filename
        if not path.exists():
            raise FileNotFoundError(f"no recorded completion: {path}")
        return path.read_text(encoding="utf-8")


def backend_from_config(cfg: dict) -> Backend:
    kind = cfg.get("backend", "ollama")
    if kind == "ollama":
        return OllamaBackend(model=cfg.get("model", "qwen2.5-coder:7b"),
                             host=cfg.get("host", "http://localhost:11434"))
    if kind == "openai":
        return OpenAICompatibleBackend()
    raise ValueError(f"unknown backend: {kind}")
