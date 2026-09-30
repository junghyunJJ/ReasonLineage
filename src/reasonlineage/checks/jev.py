"""jev (TypeSafe System One) as a checker: POST {base_url}/systemone with a state and named questions.

jev is an outside service, so it only ever sees public text: building it for a private task
is refused. The response names the model that answered; the gate compares it with the pinned
version.
"""

import asyncio
import json
import urllib.error
import urllib.request
from typing import Any, Mapping, Sequence

from .base import CheckAnswer, CheckerError, CheckResult
from .questions import Question


class JevChecker:
    name = "jev"

    def __init__(self, api_key: str, version: str, *, data_sensitivity: str,
                 base_url: str = "https://api.typesafe.ai/v1", timeout_s: float = 120.0) -> None:
        if data_sensitivity != "public":
            raise ValueError("jev is an outside service and may only check public data")
        if not api_key:
            raise ValueError("jev needs an API key")
        self.api_key = api_key
        self.pinned_version = version
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s

    def body(self, state: str, questions: Sequence[Question]) -> dict[str, Any]:
        return {"state": state, "model": self.pinned_version, "questions": {q.name: q.to_jev() for q in questions}}

    async def ask(self, state: str, questions: Sequence[Question]) -> CheckResult:
        payload = await asyncio.to_thread(self._post, self.body(state, questions))
        return parse_jev(payload, questions)

    def _post(self, body: Mapping[str, Any]) -> dict[str, Any]:
        request = urllib.request.Request(
            f"{self.base_url}/systemone",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.api_key}"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raise CheckerError(f"jev HTTP {exc.code}: {exc.read().decode(errors='replace')[:300]}") from None
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise CheckerError(f"jev request failed: {exc}") from None


def parse_jev(payload: Mapping[str, Any], questions: Sequence[Question]) -> CheckResult:
    try:
        model, raw_answers = payload["model"], payload["answers"]
    except (KeyError, TypeError):
        raise CheckerError(f"unexpected jev response: {str(payload)[:300]}") from None
    answers = {}
    for question in questions:
        raw = raw_answers.get(question.name)
        if raw is None:
            raise CheckerError(f"jev gave no answer for {question.name}")
        if question.kind == "noul":
            yes = float(raw["noul"])
            answers[question.name] = CheckAnswer("noul", {"yes": yes, "no": round(1 - yes, 4)})
        else:
            answers[question.name] = CheckAnswer(question.kind, {str(k): float(v) for k, v in raw["probabilities"].items()})
    return CheckResult(model=model, answers=answers)
