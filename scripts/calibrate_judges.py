"""Judge calibration: leniency, within-judge noise, and leave-one-out recusal bias.

Every judge scores every candidate `--repeats` times in isolated calls. The
candidates answer one drug-repurposing question at four intended quality
levels, so the run also shows whether judges agree on the ordering.

Outputs go to runs/calibration/<timestamp>/: raw.jsonl (one line per call)
and summary.json.

    python scripts/calibrate_judges.py --repeats 3 --concurrency 5
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime
from itertools import combinations
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from reasonlineage.backends import BackendError, ClaudeCLIBackend, ModelRequest  # noqa: E402
from reasonlineage.core import CATEGORY_PRESETS, composite_fitness  # noqa: E402
from reasonlineage.prompts import candidate_prompt, score_schema, strict_evaluator_system  # noqa: E402

PRESET = CATEGORY_PRESETS["biomedical"]
DIMS = list(PRESET.weights)

# (judge name, model id, effort). Haiku runs without an effort flag, as in the first smoke test.
JUDGES = [
    ("opus", "claude-opus-5-5", "high"),
    ("sonnet", "claude-sonnet-5", "high"),
    ("haiku", "claude-haiku-4-5-20251001", None),
]

QUESTION = (
    "Which of these approved drugs is most promising to repurpose for idiopathic pulmonary fibrosis (IPF)? "
    "Candidates: metformin, imatinib, sildenafil. Rank them, give the mechanism and evidence for each, "
    "and propose a validation experiment for the top pick."
)

# Intended quality order, weakest first.
CANDIDATES = {
    "weak": """1. Imatinib: it is a strong anti-cancer drug, so it should also stop fibrosis.
2. Sildenafil: it opens blood vessels, which helps breathing.
3. Metformin: a diabetes drug, probably not relevant to the lung.

Validation plan: give imatinib to IPF patients and see whether they improve.""",
    "mediocre": """1. Metformin: activates AMPK, which reverses established lung fibrosis in bleomycin mouse models by restoring myofibroblast apoptosis.
2. Sildenafil: PDE5 inhibition may improve gas exchange in IPF patients with pulmonary hypertension.
3. Imatinib: inhibits PDGFR signaling, but a randomized trial in IPF showed no benefit.

Validation plan: test metformin in precision-cut lung slices from IPF explants, measuring COL1A1 and ACTA2 expression.""",
    "good": """1. Metformin: AMPK activation restores myofibroblast apoptosis and reversed established bleomycin-induced fibrosis in mice (Rangarajan et al., Nat Med 2018). Human evidence is limited to observational data and post-hoc analyses in IPF cohorts, which have not shown a clear benefit.
2. Sildenafil: PDE5 inhibition may help patients with IPF and pulmonary hypertension, but STEP-IPF (NEJM 2010) missed its primary endpoint and INSTAGE (NEJM 2018, with nintedanib) showed no significant benefit.
3. Imatinib: PDGFR and c-Abl inhibition is antifibrotic in vitro, but a 96-week randomized trial showed no effect on disease progression (Daniels et al., AJRCCM 2010).

Validation plan: dose-response of metformin in precision-cut lung slices from IPF explants, measuring phospho-AMPK, COL1A1, and ACTA2, with nintedanib as a positive control.""",
    "strong": """Ranking, with the uncertainty stated for each:
1. Metformin (moderate confidence). Mechanism: AMPK activation restores myofibroblast apoptosis and mitochondrial biogenesis; it reversed established bleomycin-induced fibrosis in mice (Rangarajan et al., Nat Med 2018). Evidence gap: observational and post-hoc analyses in IPF cohorts show no clear benefit, and those patients took metformin for diabetes, so dose, timing, and indication are confounded. Open risk: lung tissue exposure at standard oral doses is uncertain.
2. Sildenafil (low confidence). PDE5 inhibition targets pulmonary hypertension, not fibrosis itself. STEP-IPF (NEJM 2010) missed its primary 6-minute-walk endpoint, and INSTAGE (NEJM 2018) found no significant benefit when added to nintedanib, so any remaining case is limited to a pulmonary-hypertension subgroup.
3. Imatinib (very low confidence). PDGFR and c-Abl inhibition is antifibrotic in vitro, but a 96-week randomized trial showed no effect on progression or lung function (Daniels et al., AJRCCM 2010), and nintedanib now covers the tyrosine-kinase mechanism.

Validation plan for metformin, staged with a go/no-go rule:
Stage 1: precision-cut lung slices from 6 IPF explants and 3 control lungs, metformin at 0.1-10 mM plus an AMPK-inactive control (compound C co-treatment), nintedanib as positive control. Readouts: phospho-AMPK (target engagement), COL1A1, ACTA2, and hydroxyproline. Proceed only if COL1A1 falls by at least 30% at concentrations reachable in lung tissue.
Stage 2: measure lung-to-plasma exposure in mice at human-equivalent doses before any clinical step.
Stage 3: emulate a target trial in an IPF registry, comparing metformin initiators with sulfonylurea initiators among diabetic patients, with FVC decline as the outcome.""",
}
QUALITY_ORDER = list(CANDIDATES)


async def score_all(repeats: int, concurrency: int) -> list[dict]:
    backend = ClaudeCLIBackend(max_concurrency=concurrency)
    system, schema = strict_evaluator_system(DIMS, PRESET.evaluator_emphasis), score_schema(DIMS)

    async def one(judge, model, effort, cid, repeat):
        request = ModelRequest(
            system=system, prompt=candidate_prompt(QUESTION, CANDIDATES[cid]),
            model=model, effort=effort, json_schema=schema, timeout_s=480,
        )
        record = {"judge": judge, "model": model, "effort": effort, "candidate": cid, "repeat": repeat}
        try:
            response = await backend.complete(request)
        except BackendError as exc:
            return {**record, "error": str(exc)}
        scores = {dim: response.data[dim] for dim in DIMS}
        return {
            **record,
            "scores": scores,
            "fitness": composite_fitness(scores, PRESET.weights),
            "critique": response.data["critique"],
            "duration_s": round(response.duration_s, 1),
            "cost_usd": response.cost_usd,
        }

    jobs = [one(j, m, e, c, r) for r in range(repeats) for c in CANDIDATES for j, m, e in JUDGES]
    return await asyncio.gather(*jobs)


def spearman(a: list[float], b: list[float]) -> float:
    def ranks(xs):
        order = sorted(range(len(xs)), key=lambda i: xs[i])
        result = [0.0] * len(xs)
        for rank, i in enumerate(order):
            result[i] = float(rank)
        return result
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    return 1 - 6 * sum((x - y) ** 2 for x, y in zip(ra, rb)) / (n * (n * n - 1))


def analyze(records: list[dict], repeats: int) -> dict:
    ok = [r for r in records if "fitness" in r]
    judges = [j for j, _, _ in JUDGES]

    cell = {}   # (judge, candidate) -> mean fitness
    cell_sd = {}
    for j in judges:
        for c in QUALITY_ORDER:
            values = [r["fitness"] for r in ok if r["judge"] == j and r["candidate"] == c]
            if values:
                cell[j, c] = statistics.mean(values)
                cell_sd[j, c] = statistics.stdev(values) if len(values) > 1 else 0.0
    complete = [c for c in QUALITY_ORDER if all((j, c) in cell for j in judges)]

    # Additive model: fitness = candidate effect + judge offset + interaction + noise.
    cand_mean = {c: statistics.mean(cell[j, c] for j in judges) for c in complete}
    offset = {j: statistics.mean(cell[j, c] - cand_mean[c] for c in complete) for j in judges}
    residuals = [cell[j, c] - cand_mean[c] - offset[j] for j in judges for c in complete]
    dof = (len(judges) - 1) * (len(complete) - 1)
    interaction_sd = (sum(r * r for r in residuals) / dof) ** 0.5 if dof else 0.0
    noise_sd = {j: statistics.mean(cell_sd[j, c] ** 2 for c in complete) ** 0.5 for j in judges}

    # Leave-one-out recusal: candidate authored by `a` is judged by everyone else.
    def loo_bias(calibrated: bool) -> dict:
        def value(j, c):
            return cell[j, c] - (offset[j] if calibrated else 0.0)
        out = {}
        for a in judges:
            panel = [j for j in judges if j != a]
            full = {c: statistics.mean(value(j, c) for j in judges) for c in complete}
            out[a] = statistics.mean(statistics.mean(value(j, c) for j in panel) - full[c] for c in complete)
        return out

    # Interaction larger than the noise of a cell mean means leniency is not a constant offset.
    noise_of_mean = statistics.mean(noise_sd.values()) / repeats ** 0.5
    ranking = {j: [cell[j, c] for c in complete] for j in judges}
    intended = list(range(len(complete)))
    return {
        "calls": len(records),
        "errors": [r for r in records if "error" in r],
        "repeats": repeats,
        "cell_mean": {f"{j}/{c}": round(cell[j, c], 3) for j in judges for c in complete},
        "cell_sd": {f"{j}/{c}": round(cell_sd[j, c], 3) for j in judges for c in complete},
        "candidate_mean": {c: round(v, 3) for c, v in cand_mean.items()},
        "judge_offset": {j: round(v, 3) for j, v in offset.items()},
        "within_judge_noise_sd": {j: round(v, 3) for j, v in noise_sd.items()},
        "interaction_sd": round(interaction_sd, 3),
        "interaction_vs_noise_of_mean": round(interaction_sd / noise_of_mean, 2) if noise_of_mean else None,
        "spearman_vs_intended_order": {j: round(spearman(ranking[j], intended), 2) for j in judges},
        "spearman_between_judges": {
            f"{a}~{b}": round(spearman(ranking[a], ranking[b]), 2) for a, b in combinations(judges, 2)
        },
        "loo_recusal_bias_raw": {j: round(v, 3) for j, v in loo_bias(False).items()},
        "loo_recusal_bias_offset_corrected": {j: round(v, 3) for j, v in loo_bias(True).items()},
        "mean_call_s": {
            j: round(statistics.mean(r["duration_s"] for r in ok if r["judge"] == j), 1) for j in judges
        },
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()

    started = time.monotonic()
    records = asyncio.run(score_all(args.repeats, args.concurrency))
    out = Path("runs/calibration") / f"{datetime.now():%Y%m%d-%H%M%S}"
    out.mkdir(parents=True, exist_ok=True)
    with (out / "raw.jsonl").open("w") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    summary = {"wall_s": round(time.monotonic() - started, 1), **analyze(records, args.repeats)}
    (out / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    print(f"saved {out}")
