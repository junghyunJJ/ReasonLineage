"""Models served by vLLM's OpenAI-compatible API (the local Qwen and DeepSeek).

Isolation comes from the request itself: one system message, one user message, and no
`tools`. `reasoning_effort` is sent whenever it is set, because Qwen reasons at full length
when it is left out (2026-09-29). A JSON schema goes through `response_format` in strict mode.
"""

import asyncio
import json
import re
import time
import urllib.error
import urllib.request
from typing import Any, Mapping

from ._subprocess import response, structured_data
from .base import BackendError, ModelRequest, ModelResponse

_THINK = re.compile(r"^\s*<think>.*?</think>\s*", re.S)
_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


def clean_content(text: str) -> str:
    """Drop a leading <think> block and a surrounding code fence, which some servers leave in."""
    text = _THINK.sub("", text)
    fenced = _FENCE.match(text)
    return fenced.group(1) if fenced else text


class HttpBackend:
    def __init__(self, name: str, base_url: str, max_concurrency: int = 2, retries: int = 0, api_key: str = "EMPTY") -> None:
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.retries = retries
        self.api_key = api_key
        self._semaphore = asyncio.Semaphore(max_concurrency)

    def build_body(self, request: ModelRequest) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": request.model,
            "messages": [
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
        }
        if request.max_tokens is not None:
            body["max_tokens"] = request.max_tokens
        if request.effort:
            body["reasoning_effort"] = request.effort
        if request.seed is not None:
            body["seed"] = request.seed
        if request.json_schema is not None:
            body["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": dict(request.json_schema), "strict": True},
            }
        if request.top_logprobs is not None:
            body["logprobs"] = True
            body["top_logprobs"] = request.top_logprobs
        return body

    async def complete(self, request: ModelRequest) -> ModelResponse:
        errors = []
        for _ in range(self.retries + 1):
            try:
                async with self._semaphore:
                    return await self._run_once(request)
            except BackendError as exc:
                errors.append(str(exc))
        raise BackendError(f"{self.name}/{request.model} failed after {len(errors)} attempt(s): {errors}")

    async def _run_once(self, request: ModelRequest) -> ModelResponse:
        started = time.monotonic()
        payload = await asyncio.to_thread(self._send, "/chat/completions", self.build_body(request), request.timeout_s)
        return self.parse(payload, request, time.monotonic() - started)

    def _send(self, path: str, body: Mapping[str, Any] | None, timeout_s: float) -> dict[str, Any]:
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(
            self.base_url + path,
            data=data,
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_s) as resp:
                return json.load(resp)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode(errors="replace")[:400]
            raise BackendError(f"HTTP {exc.code}: {detail}") from None
        except json.JSONDecodeError as exc:
            raise BackendError(f"response is not JSON: {exc}") from None
        except (urllib.error.URLError, OSError) as exc:
            raise BackendError(f"request to {self.base_url} failed: {exc}") from None

    def parse(self, payload: Mapping[str, Any], request: ModelRequest, duration_s: float) -> ModelResponse:
        try:
            choice = payload["choices"][0]
            message = choice["message"]
        except (KeyError, IndexError, TypeError):
            raise BackendError(f"unexpected response: {str(payload)[:300]!r}") from None
        if choice.get("finish_reason") == "length":
            raise BackendError("output was cut off at max_tokens")
        text = clean_content(message.get("content") or "")
        data = structured_data(request, None, text)
        raw = {
            "usage": payload.get("usage") or {},
            "reasoning": message.get("reasoning") or message.get("reasoning_content"),
            "logprobs": (choice.get("logprobs") or {}).get("content"),
            "finish_reason": choice.get("finish_reason"),
            "served_model": payload.get("model"),
        }
        return response(self.name, request, text, data, duration_s, None, raw)

    def served_models(self, timeout_s: float = 20.0) -> list[str]:
        payload = self._send("/models", None, timeout_s)
        try:
            return [entry["id"] for entry in payload["data"]]
        except (KeyError, TypeError):
            raise BackendError(f"unexpected model list from {self.base_url}: {str(payload)[:200]}") from None
