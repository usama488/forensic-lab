"""Forensic toxicology & pathology calculators.

- Widmark blood-alcohol estimation (with Watson total-body-water option) and retrograde extrapolation.
- Post-mortem interval from body temperature: Henssge (1988) double-exponential model and the classic Glaister rule.
These are textbook approximations with wide uncertainty; casework requires a qualified expert.
"""
from __future__ import annotations

import math

import numpy as np

ETHANOL_DENSITY = 0.789  # g/mL
DRINKS = {"Beer 330 mL (5%)": (330, 5.0), "Strong beer 500 mL (8%)": (500, 8.0), "Wine glass 150 mL (12.5%)": (150, 12.5),
          "Spirits shot 40 mL (40%)": (40, 40.0), "Custom": (100, 10.0)}
LIMITS = {"USA / UK (England & Wales) 0.08 g/100 mL": .08, "Most of EU / Australia 0.05": .05, "Norway / Sweden / Poland 0.02": .02,
          "Commercial / novice drivers (many countries) 0.02": .02}


def grams(volume_ml: float, abv: float) -> float:
    return volume_ml * abv / 100 * ETHANOL_DENSITY


def widmark_r(sex: str, weight=None, height=None, age=None, method="Widmark (classic)") -> float:
    if method.startswith("Watson") and weight and height and age:
        tbw = (2.447 - 0.09516 * age + 0.1074 * height + 0.3362 * weight) if sex == "Male" else (-2.097 + 0.1069 * height + 0.2466 * weight)
        return tbw / (0.8 * weight)  # 0.8 = water fraction of blood
    return 0.68 if sex == "Male" else 0.55


def bac_curve(alcohol_g: float, weight: float, r: float, hours: float, beta=0.15, ka=4.0, start=0.0):
    """BAC in g/kg (‰) over time; first-order absorption then zero-order elimination (beta ‰/h)."""
    t = np.linspace(0, hours, 400)
    c0 = alcohol_g / (r * weight)
    tt = np.clip(t - start, 0, None)
    absorbed = c0 * (1 - np.exp(-ka * tt))
    bac = np.zeros_like(t)
    level = 0.0
    prev_abs = 0.0
    for i in range(1, len(t)):
        dt_ = t[i] - t[i - 1]
        level += absorbed[i] - prev_abs
        prev_abs = absorbed[i]
        level = max(level - beta * dt_ if level > 0 else 0.0, 0.0)
        bac[i] = level
    return t, bac


def retrograde(measured_g100: float, hours_between: float, beta_min=.10, beta_max=.25) -> tuple[float, float]:
    """Estimate BAC at the time of the incident (assumes absorption was complete). Input/output in g/100 mL; beta in ‰/h."""
    return measured_g100 + beta_min / 10 * hours_between, measured_g100 + beta_max / 10 * hours_between


def henssge(rectal: float, ambient: float, weight: float, cf: float = 1.0) -> dict:
    """Solve Henssge's nomogram equation for time since death (hours)."""
    if rectal <= ambient:
        return {"hours": None, "note": "Rectal temperature is at/below ambient: body has equilibrated (likely > 24-48 h)."}
    q = (rectal - ambient) / (37.2 - ambient)
    b = -1.2815 * (cf * weight) ** -0.625 + 0.0284
    if ambient <= 23:
        f = lambda t: 1.25 * math.exp(b * t) - 0.25 * math.exp(5 * b * t) - q  # noqa: E731
    else:
        f = lambda t: 1.11 * math.exp(b * t) - 0.11 * math.exp(10 * b * t) - q  # noqa: E731
    if q >= 1:
        return {"hours": 0.0, "q": q, "note": "Body still at normal temperature (plateau phase, < ~2-3 h)."}
    lo, hi = 0.0, 200.0
    for _ in range(100):
        mid = (lo + hi) / 2
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    t = (lo + hi) / 2
    ci = 2.8 if t <= 15 else 4.5 if t <= 30 else 7.0
    return {"hours": t, "q": q, "B": b, "ci95": ci,
            "note": f"95% interval ±{ci} h (Henssge; larger when conditions are non-standard). Valid for ambient ≤ 23 °C or > 23 °C with the alternative constants."}


def glaister(rectal_c: float) -> float:
    rectal_f = rectal_c * 9 / 5 + 32
    return (98.4 - rectal_f) / 1.5


CORRECTIVE = {"Naked, dry, still air": 1.0, "Naked, moving air": .75, "Naked, wet body, still water": .5, "Naked, flowing water": .35,
              "1-2 thin layers of clothing, still air": 1.1, "2-3 layers / thin blanket": 1.3, "Thick bedding / duvet": 1.8,
              "Heavy bedding (multiple duvets)": 2.4}

POSTMORTEM_SIGNS = [
    ("Algor mortis (cooling)", "Plateau 0.5-3 h, then ~0.5-1.5 °C/h depending on conditions", "0-24 h"),
    ("Livor mortis (lividity)", "Visible 0.5-2 h; maximal 6-12 h; becomes fixed (non-blanching) after ~8-12 h", "0.5-12 h"),
    ("Rigor mortis", "Onset 2-6 h (jaw first), full 6-12 h, persists, resolves 24-48 h (faster in heat)", "2-48 h"),
    ("Corneal clouding", "Eyes open ~2 h; eyes closed ~24 h", "2-24 h"),
    ("Early decomposition", "Green discolouration of right iliac fossa ~24-48 h; marbling ~3-4 days; bloating ~3-7 days", "1-7 days"),
    ("Entomology", "Blowfly eggs within hours of death if accessible; larval stage gives minimum PMI (days-weeks)", "hours-weeks"),
]
