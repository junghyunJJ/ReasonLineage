"""Synthetic hidden-law gold set (gold synth design).

Each task shows noisy data drawn from one of three candidate biological models and asks which model made them.
The data are drawn afresh, so the answer is written nowhere. A task is kept only when the data support the true
model: its posterior among the three candidates, fitted to the data the models see, lies in the chosen band.
"""

import hashlib
import json
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np
from scipy.optimize import OptimizeWarning, curve_fit

from .build import shuffled


@dataclass(frozen=True)
class Model:
    name: str
    formula: str
    f: Callable[..., np.ndarray]
    params: tuple[str, ...]  # names of f's parameters after x, as generation.json records them


@dataclass(frozen=True)
class Family:
    key: str
    context: str
    columns: tuple[str, ...]  # table headers: the x columns, then the measured value
    unit: str  # unit of the measured value, for the error SD
    x: np.ndarray  # shape (n,) or (columns - 1, n)
    models: tuple[Model, Model, Model]
    sample: Callable[[np.random.Generator, int], tuple[float, ...]]  # true parameters for model i
    starts: Callable[[np.ndarray, np.ndarray], list[tuple[float, ...]]]  # fit starting points from the data


# --- dose-response: drug concentration (µM) -> effect (% of maximum) ---

def hyperbolic(c, emax, ec50):
    return emax * c / (ec50 + c)


def sigmoid(c, emax, ec50):
    return emax * c**2 / (ec50**2 + c**2)


def loglinear(c, m, c0):
    return m * np.log(c / c0)


def _dose_sample(rng, i):
    top = rng.uniform(60, 100)
    if i < 2:
        return top, float(np.exp(rng.uniform(np.log(0.1), np.log(10))))
    c0 = float(np.exp(rng.uniform(np.log(0.001), np.log(0.008))))
    return top / np.log(100 / c0), c0


def _dose_starts(x, y):
    top = max(float(y.max()), 1e-3)
    sat = [(top * k, float(e)) for k in (1.0, 1.5) for e in (0.1, 1.0, 10.0)]
    lin = [(top / np.log(x.max() / c0), c0) for c0 in (1e-4, 1e-3, 5e-3)]
    return sat + lin


DOSE = Family(
    key="dose",
    context="Cultured cells were exposed to a drug at 10 concentrations, and the drug effect was measured as a "
            "percentage of the maximal possible effect.",
    columns=("concentration (µM)", "effect (% of maximum)"), unit="%",
    x=np.array([float(f"{c:.3g}") for c in np.logspace(-2, 2, 10)]),  # as the table shows them
    models=(Model("Hyperbolic Emax model", "E = Emax·C/(EC50 + C)", hyperbolic, ("Emax", "EC50")),
            Model("Sigmoid Emax model (Hill coefficient 2)", "E = Emax·C²/(EC50² + C²)", sigmoid, ("Emax", "EC50")),
            Model("Log-linear model", "E = m·ln(C/C0)", loglinear, ("m", "C0"))),
    sample=_dose_sample, starts=_dose_starts)


# --- enzyme inhibition: substrate S and inhibitor I (µM) -> initial velocity (µM/min) ---

def competitive(x, vmax, km, ki):
    s, i = x
    return vmax * s / (km * (1 + i / ki) + s)


def noncompetitive(x, vmax, km, ki):
    s, i = x
    return vmax * s / ((km + s) * (1 + i / ki))


def uncompetitive(x, vmax, km, ki):
    s, i = x
    return vmax * s / (km + s * (1 + i / ki))


INHIBITOR = 10.0
_S = np.round(np.logspace(0, np.log10(200), 8), 1)


def _enzyme_sample(rng, i):
    return (rng.uniform(10, 50), float(np.exp(rng.uniform(np.log(5), np.log(40)))),
            float(np.exp(rng.uniform(np.log(2), np.log(20)))))


def _enzyme_starts(x, y):
    top = max(float(y.max()), 1e-3)
    return [(top * k, km, ki) for k in (1.0, 2.0) for km in (5.0, 30.0) for ki in (2.0, 20.0)]


ENZYME = Family(
    key="enzyme",
    context=f"The initial velocity of a purified enzyme was measured at 8 substrate concentrations, without "
            f"inhibitor and with an inhibitor at {INHIBITOR:g} µM.",
    columns=("substrate (µM)", "inhibitor (µM)", "initial velocity (µM/min)"), unit="µM/min",
    x=np.vstack([np.tile(_S, 2), np.repeat([0.0, INHIBITOR], len(_S))]),
    models=(Model("Competitive inhibition", "v = Vmax·S/(Km·(1 + I/Ki) + S)", competitive, ("Vmax", "Km", "Ki")),
            Model("Noncompetitive inhibition", "v = Vmax·S/((Km + S)·(1 + I/Ki))", noncompetitive,
                  ("Vmax", "Km", "Ki")),
            Model("Uncompetitive inhibition", "v = Vmax·S/(Km + S·(1 + I/Ki))", uncompetitive, ("Vmax", "Km", "Ki"))),
    sample=_enzyme_sample, starts=_enzyme_starts)


# --- cell growth: time (h) -> OD600 ---

def logistic(t, n0, r, k):
    return k / (1 + (k - n0) / n0 * np.exp(-r * t))


def gompertz(t, n0, r, k):
    return k * np.exp(np.log(n0 / k) * np.exp(-r * t))


def monomolecular(t, n0, r, k):
    return k - (k - n0) * np.exp(-r * t)


_GROWTH_RATE = ((0.15, 0.4), (0.06, 0.2), (0.07, 0.2))


def _growth_sample(rng, i):
    return rng.uniform(0.02, 0.08), rng.uniform(*_GROWTH_RATE[i]), rng.uniform(0.8, 1.5)


def _growth_starts(x, y):
    n0, k = max(float(y[0]), 1e-3), max(float(y.max()), 2e-3)
    return [(n0, r, k) for r in (0.05, 0.1, 0.2, 0.4)]


GROWTH = Family(
    key="growth",
    context="A bacterial culture was grown in batch, and its optical density (OD600) was measured every 4 hours.",
    columns=("time (h)", "OD600"), unit="OD units",
    x=np.arange(0.0, 48.0, 4.0),
    models=(Model("Logistic growth", "N = K/(1 + ((K − N0)/N0)·e^(−r·t))", logistic, ("N0", "r", "K")),
            Model("Gompertz growth", "N = K·exp(ln(N0/K)·e^(−r·t))", gompertz, ("N0", "r", "K")),
            Model("Monomolecular growth", "N = K − (K − N0)·e^(−r·t)", monomolecular, ("N0", "r", "K"))),
    sample=_growth_sample, starts=_growth_starts)


# --- drug elimination: time after an intravenous dose (h) -> plasma concentration (mg/L) ---

def first_order(t, c0, k):
    return c0 * np.exp(-k * t)


def zero_order(t, c0, k0):
    return np.maximum(c0 - k0 * t, 0.0)


def second_order(t, c0, k2):
    return c0 / (1 + c0 * k2 * t)


_T_END = 12.0


def _elimination_sample(rng, i):
    c0, left = rng.uniform(5, 50), rng.uniform(0.05, 0.3)  # share of the dose left at the last sample
    rate = (-np.log(left) / _T_END, (1 - left) * c0 / _T_END, (1 / left - 1) / (_T_END * c0))[i]
    return c0, rate


def _elimination_starts(x, y):
    # A dense grid: the zero-order model's kink traps a fit started far away (checked against random restarts).
    c0 = max(float(y[0]), 1e-3)
    return [(c * c0, rate) for c in np.linspace(0.6, 2.0, 15) for rate in np.logspace(-4, 1, 40)]


ELIMINATION = Family(
    key="elimination",
    context="After a single intravenous bolus dose of a drug, its plasma concentration was measured at 10 time points.",
    columns=("time (h)", "plasma concentration (mg/L)"), unit="mg/L",
    x=np.array([0.5, 1, 1.5, 2, 3, 4, 6, 8, 10, 12.0]),
    models=(Model("First-order elimination", "C = C0·e^(−k·t)", first_order, ("C0", "k")),
            Model("Zero-order elimination", "C = max(C0 − k0·t, 0)", zero_order, ("C0", "k0")),
            Model("Second-order elimination", "C = C0/(1 + C0·k2·t)", second_order, ("C0", "k2"))),
    sample=_elimination_sample, starts=_elimination_starts)


FAMILIES: tuple[Family, ...] = (DOSE, ENZYME, GROWTH, ELIMINATION)
# The true model's posterior for each band (gold synth design 4.3): low bound inclusive, high bound exclusive.
BANDS: dict[str, tuple[float, float]] = {"easy": (0.999, 1.01), "medium": (0.97, 0.999), "hard": (0.90, 0.97)}
FIT_FROM = 8  # starting points refined per model


def round3(values: np.ndarray) -> np.ndarray:
    """Values rounded to 3 significant digits, as the task shows them."""
    return np.array([float(f"{v:.3g}") for v in np.ravel(values)]).reshape(np.shape(values))


def fit(model: Model, family: Family, y: np.ndarray) -> tuple[float, tuple[float, ...]] | None:
    """The least residual sum of squares of `model` on the data, with its parameters.

    Refines the FIT_FROM starting points with the lowest residuals; parameters stay positive. None when no start
    converges.
    """
    def rss(p):
        with np.errstate(all="ignore"):
            return float(np.sum((model.f(family.x, *p) - y) ** 2))

    scored = sorted((r, p0) for p0 in family.starts(family.x, y) if np.isfinite(r := rss(p0)))
    best = None
    for _, p0 in scored[:FIT_FROM]:
        try:
            with warnings.catch_warnings(), np.errstate(all="ignore"):
                warnings.simplefilter("ignore", OptimizeWarning)
                p, _ = curve_fit(model.f, family.x, y, p0=p0, bounds=(1e-9, np.inf), maxfev=5000)
        except (RuntimeError, ValueError):
            continue
        r = rss(p)
        if np.isfinite(r) and (best is None or r < best[0]):
            best = (r, tuple(float(v) for v in p))
    return best


def posteriors(family: Family, y: np.ndarray, sigma: float) -> list[dict[str, Any]] | None:
    """Each candidate's fit and posterior, in the family's model order; None when any fit fails.

    The three models have the same number of parameters, so the BIC weights reduce to exp(−RSS/2σ²) (design 4.3).
    """
    fits = [fit(model, family, y) for model in family.models]
    if any(f is None for f in fits):
        return None
    rss = np.array([f[0] for f in fits])
    logw = -(rss - rss.min()) / (2 * sigma**2)
    w = np.exp(logw) / np.exp(logw).sum()
    return [{"model": m.name, "rss": round(f[0], 6), "posterior": float(p), "params": [round(v, 6) for v in f[1]]}
            for m, f, p in zip(family.models, fits, w)]


def band_of(posterior: float) -> str | None:
    for band, (low, high) in BANDS.items():
        if low <= posterior < high:
            return band
    return None


class SynthError(RuntimeError):
    """A set could not be built: a band could not be filled, or the task folder holds files it does not build."""


MAX_TRIES = 2000  # draws per task before giving up (design 7)


def _rng(set_name: str, index: int) -> np.random.Generator:
    return np.random.default_rng(int(hashlib.sha256(f"{set_name}:{index}".encode("utf-8")).hexdigest()[:16], 16))


def assignment(index: int) -> tuple[Family, int]:
    """Task `index`'s family and true model: families in turn, and each family's true models in turn (design 4.4)."""
    family = FAMILIES[index % len(FAMILIES)]
    return family, (index // len(FAMILIES)) % 3


def draw(family: Family, truth: int, band: str, rng: np.random.Generator) -> dict[str, Any] | None:
    """One draw of data from the true model; None when it is discarded (design 4.2, 4.3)."""
    params = family.sample(rng, truth)
    clean = family.models[truth].f(family.x, *params)
    sigma = float(f"{rng.uniform(0.02, 0.10) * float(np.max(clean)):.3g}")
    # Readings below zero stay: dropping them would make the error near zero half-normal, not the stated Gaussian.
    y = round3(clean + rng.normal(0.0, sigma, size=np.shape(clean)))
    fits = posteriors(family, y, sigma)
    if fits is None or band_of(fits[truth]["posterior"]) != band:
        return None
    return {"params": [float(v) for v in params], "sigma": sigma, "y": y, "fits": fits}


def _number(v: float) -> str:
    return f"{v:.3g}"


def question(family: Family, y: np.ndarray, sigma: float, order: list[str]) -> str:
    formulas = {m.name: m.formula for m in family.models}
    xs = family.x if family.x.ndim == 2 else family.x[None, :]
    rows = ["| " + " | ".join(family.columns) + " |", "|" + " --- |" * len(family.columns)]
    rows += ["| " + " | ".join([*(_number(x[j]) for x in xs), _number(y[j])]) + " |" for j in range(len(y))]
    lines = [f"{family.context} Measurement error is Gaussian with SD {_number(sigma)} {family.unit}.", "Data:", *rows,
             "Candidate models (parameters unknown, all positive):", *(f"- {name}: {formulas[name]}" for name in order),
             "Which candidate model most likely generated these data? Rank the candidates, and give the features of "
             "the data that decide it, the key evidence, and one further measurement that would best confirm the "
             "top pick."]
    return "\n".join(lines)


def make_task(set_name: str, index: int, band: str) -> dict[str, Any]:
    """Task `index` of the set: its task file body, gold entry and generation record (design 4.2–4.4)."""
    family, truth = assignment(index)
    rng = _rng(set_name, index)
    task_id = f"{set_name}-{index + 1:02d}"
    for tries in range(1, MAX_TRIES + 1):
        drawn = draw(family, truth, band, rng)
        if drawn is not None:
            break
    else:
        raise SynthError(f"{task_id}: no {family.key} data with the true model's posterior in band {band!r} "
                         f"after {MAX_TRIES} draws")
    names = [m.name for m in family.models]
    order = shuffled(names, task_id)
    body = {"id": task_id, "question": question(family, drawn["y"], drawn["sigma"], order), "candidates": order,
            "category": "analytical", "data_sensitivity": "public"}
    gold = {"approved": [names[truth]], "failed": sorted(n for i, n in enumerate(names) if i != truth)}
    params = dict(zip(family.models[truth].params, drawn["params"]))
    record = {"family": family.key, "truth": names[truth], "params": params, "sigma": drawn["sigma"], "tries": tries,
              "fits": drawn["fits"]}
    return {"task": body, "gold": gold, "record": record}


def build(set_name: str, band: str, count: int, tasks_dir: str | Path, gold_dir: str | Path) -> list[Path]:
    """Write `count` task files, gold.json and generation.json; nothing is written if a task cannot be made
    or the task folder holds files this build does not make (design 4.4, 7)."""
    if band not in BANDS:
        raise SynthError(f"unknown band {band!r}; use one of {sorted(BANDS)}")
    tasks_dir, gold_dir = Path(tasks_dir), Path(gold_dir)
    ids = [f"{set_name}-{i + 1:02d}" for i in range(count)]
    stale = [f"{path} is not built by this set; delete it, then build again"
             for path in sorted(tasks_dir.glob("*.json")) if path.stem not in ids]
    if stale:
        raise SynthError("; ".join(stale))
    made = [make_task(set_name, i, band) for i in range(count)]
    tasks_dir.mkdir(parents=True, exist_ok=True)
    gold_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for task in made:
        path = tasks_dir / f"{task['task']['id']}.json"
        path.write_text(json.dumps(task["task"], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        written.append(path)
    source = {"generator": "reasonlineage.gold.synth", "set": set_name, "band": band}
    gold = {"source": source, "tasks": {t["task"]["id"]: t["gold"] for t in made}}
    generation = {"source": source, "tasks": {t["task"]["id"]: t["record"] for t in made}}
    for name, body in (("gold.json", gold), ("generation.json", generation)):
        (gold_dir / name).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return written
