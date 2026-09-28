"""Live roster check: one isolated scoring call per backend/model, reporting context size and latency.

    python scripts/check_backends.py claude:claude-opus-5-5:xhigh codex:gpt-6-astra:xhigh grok:grok-4.7:xhigh

Input tokens are the isolation signal: a call that loaded user instructions,
skills, or tool schemas shows a much larger context than the prompt needs.
"""

import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reasonlineage.backends import (  # noqa: E402
    BackendError,
    ClaudeCLIBackend,
    CodexCLIBackend,
    GrokCLIBackend,
    ModelRequest,
)

BACKENDS = {"claude": ClaudeCLIBackend, "codex": CodexCLIBackend, "grok": GrokCLIBackend}
SCHEMA = {
    "type": "object",
    "properties": {"accuracy": {"type": "number", "minimum": 0, "maximum": 1}, "critique": {"type": "string"}},
    "required": ["accuracy", "critique"],
    "additionalProperties": False,
}
PROMPT = ('Candidate answer: "Metformin lowers blood glucose mainly by increasing insulin secretion '
          'from pancreatic beta cells." Score its accuracy from 0 to 1 and give one critique sentence.')


def input_tokens(raw) -> int | None:
    """Whole context the model read. Claude and Grok report cache reads separately; Codex's
    cached_input_tokens is already part of input_tokens."""
    usage = raw.get("usage") or {}
    if "input_tokens" not in usage:
        return None
    return usage["input_tokens"] + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0)


async def check(spec: str) -> str:
    kind, model, *rest = spec.split(":")
    effort = rest[0] if rest else None
    backend = BACKENDS[kind](retries=0)
    request = ModelRequest(system="You are a strict evaluator.", prompt=PROMPT, model=model,
                           effort=effort, json_schema=SCHEMA, timeout_s=600)
    try:
        r = await backend.complete(request)
    except BackendError as exc:
        return f"FAIL  {spec:40} {str(exc)[:160]}"
    return (f"ok    {spec:40} {r.duration_s:6.1f}s  input_tokens={input_tokens(r.raw)}  "
            f"accuracy={r.data['accuracy']}")


async def main(specs: list[str]) -> None:
    for line in await asyncio.gather(*(check(s) for s in specs)):
        print(line)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("specs", nargs="+", help="backend:model[:effort]")
    asyncio.run(main(parser.parse_args().specs))
