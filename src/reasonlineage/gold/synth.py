"""Synthetic hidden-law gold set (gold synth design).

Each task shows noisy data drawn from one of three candidate biological models and asks which model made them.
The data are drawn afresh, so the answer is written nowhere. A task is kept only when the data support the true
model: its posterior among the three candidates, fitted to the data the models see, lies in the chosen band.
"""

from dataclasses import dataclass
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class Model:
    name: str
    formula: str
    f: Callable[..., np.ndarray]


@dataclass(frozen=True)
class Family:
    key: str
    context: str
    columns: tuple[str, ...]  # table headers: the x columns, then the measured value
    unit: str  # unit of the measured value, for the error SD
    x: np.ndarray  # shape (n,) or (columns - 1, n)
    params: tuple[str, ...]
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
    x=np.logspace(-2, 2, 10),
    params=("Emax", "EC50"),
    models=(Model("Hyperbolic Emax model", "E = Emax·C/(EC50 + C)", hyperbolic),
            Model("Sigmoid Emax model (Hill coefficient 2)", "E = Emax·C²/(EC50² + C²)", sigmoid),
            Model("Log-linear model", "E = m·ln(C/C0)", loglinear)),
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
    params=("Vmax", "Km", "Ki"),
    models=(Model("Competitive inhibition", "v = Vmax·S/(Km·(1 + I/Ki) + S)", competitive),
            Model("Noncompetitive inhibition", "v = Vmax·S/((Km + S)·(1 + I/Ki))", noncompetitive),
            Model("Uncompetitive inhibition", "v = Vmax·S/(Km + S·(1 + I/Ki))", uncompetitive)),
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
    params=("N0", "r", "K"),
    models=(Model("Logistic growth", "N = K/(1 + ((K − N0)/N0)·e^(−r·t))", logistic),
            Model("Gompertz growth", "N = K·exp(ln(N0/K)·e^(−r·t))", gompertz),
            Model("Monomolecular growth", "N = K − (K − N0)·e^(−r·t)", monomolecular)),
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
    params=("C0", "k"),
    models=(Model("First-order elimination", "C = C0·e^(−k·t)", first_order),
            Model("Zero-order elimination", "C = max(C0 − k0·t, 0)", zero_order),
            Model("Second-order elimination", "C = C0/(1 + C0·k2·t)", second_order)),
    sample=_elimination_sample, starts=_elimination_starts)


FAMILIES: tuple[Family, ...] = (DOSE, ENZYME, GROWTH, ELIMINATION)
