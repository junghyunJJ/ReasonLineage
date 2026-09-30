"""Generate author-balanced calibration candidates: every roster model writes one strong and
one deliberately flawed answer to the same question, in isolated calls.

    python scripts/make_candidates.py opus=claude:claude-opus-5-5:xhigh sonnet=claude:claude-sonnet-5-5:xhigh \
        gpt=codex:gpt-6.1-sol:xhigh grok=grok:grok-4.7:xhigh

Writes runs/calibration/candidates-<timestamp>.json. With --into FILE --only ID,ID it regenerates
just those candidates and replaces them in FILE.

Two author behaviors seen on 2026-09-27 are handled here: a Claude safety-classifier
refusal on this benign question (retried), and a weak answer wrapped in
"=== SYNTHETIC ... ===" marker lines (the body between the markers is kept and the
step is recorded in the candidate's "postprocess" field).
"""

import argparse
import asyncio
import json
import re
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reasonlineage.backends import BackendError, ModelRequest  # noqa: E402
from reasonlineage.backends.roster import make_backend, parse_entry  # noqa: E402

QUESTION = (
    "Which of these approved drugs is most promising to repurpose for idiopathic pulmonary fibrosis (IPF)? "
    "Candidates: metformin, imatinib, sildenafil. Rank them, give the mechanism and evidence for each, "
    "and propose a validation experiment for the top pick."
)

SYSTEM = "You are an expert in translational pharmacology. Answer in plain text without markdown headers."

INSTRUCTIONS = {
    "strong": (
        "Write your best answer. Rank the three drugs; for each give the mechanism and the key preclinical "
        "and human evidence, naming specific trials or studies only where you are confident they exist; "
        "state the main uncertainty; and propose a validation experiment for the top pick with controls "
        "and readouts. Length: 200-300 words."
    ),
    "weak": (
        "This answer is a test item for calibrating evaluators, so it must contain three specific flaws: "
        "(1) do not mention any clinical trial results, positive or negative; (2) state mechanisms as facts "
        "without citing any study; (3) give a validation plan that names no controls, readouts, or doses. "
        "Otherwise write naturally and confidently, as if it were a real answer, and do not signal that "
        "anything is missing. Length: 200-300 words."
    ),
}


REFUSAL = re.compile(r"safety classifier|can't regenerate that answer", re.I)
MARKER = re.compile(r"^={3,}.*={3,}\s*$", re.M)


def extract_marked_body(text: str) -> tuple[str, str | None]:
    """Keep only the body between the first two marker lines, if the author added them."""
    parts = MARKER.split(text)
    if len(parts) >= 3:
        return parts[1].strip(), "kept body between author's === marker lines"
    return text, None


async def main(specs: list[str], only: set[str] | None, into: Path | None, attempts: int = 3) -> Path:
    entries = [parse_entry(s) for s in specs]

    async def write(entry, level):
        backend = make_backend(entry)
        prompt = f"Question:\n{QUESTION}\n\n{INSTRUCTIONS[level]}"
        request = ModelRequest(system=SYSTEM, prompt=prompt, model=entry.model, effort=entry.effort, timeout_s=900)
        refusals = 0
        for _ in range(attempts):
            try:
                response = await backend.complete(request)
            except BackendError as exc:
                return {"id": f"{entry.name}-{level}", "author": entry.name, "level": level, "error": str(exc)}
            if not REFUSAL.search(response.text):
                break
            refusals += 1
        else:
            return {"id": f"{entry.name}-{level}", "author": entry.name, "level": level,
                    "error": f"refused {refusals} times: {response.text[:200]}"}
        text, postprocess = extract_marked_body(response.text.strip())
        return {
            "id": f"{entry.name}-{level}",
            "author": entry.name,
            "family": entry.family,
            "level": level,
            "model": entry.model,
            "effort": entry.effort,
            "words": len(text.split()),
            "duration_s": round(response.duration_s, 1),
            "refusals_before_answer": refusals,
            "postprocess": postprocess,
            "text": text,
        }

    jobs = [(e, level) for e in entries for level in INSTRUCTIONS if only is None or f"{e.name}-{level}" in only]
    fresh = await asyncio.gather(*(write(e, level) for e, level in jobs))
    if into is not None:
        data = json.loads(into.read_text())
        replaced = {c["id"]: c for c in fresh}
        data["candidates"] = [replaced.get(c["id"], c) for c in data["candidates"]]
        into.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        return into
    out = Path("runs/calibration") / f"candidates-{datetime.now():%Y%m%d-%H%M%S}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"question": QUESTION, "candidates": fresh}, indent=2, ensure_ascii=False))
    return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("roster", nargs="+", help="name=backend:model[:effort]")
    parser.add_argument("--only", help="comma-separated candidate ids to (re)generate")
    parser.add_argument("--into", type=Path, help="existing candidates file to update in place")
    args = parser.parse_args()
    path = asyncio.run(main(args.roster, set(args.only.split(",")) if args.only else None, args.into))
    data = json.loads(path.read_text())
    for c in data["candidates"]:
        status = f"ERROR {c['error'][:120]}" if "error" in c else f"{c['words']:4d} words  {c['duration_s']:6.1f}s"
        print(f"{c['id']:14} {status}")
    print(f"saved {path}")
