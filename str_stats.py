"""Forensic STR statistics.

Allele frequencies: norSTR v2023 databases (Department of Forensic Sciences, Oslo University Hospital; MIT licence),
7 populations, 32-50 autosomal STR markers each.

Implements: profile comparison, random match probability (product rule, NRC II 4.1, Balding-Nichols NRC II 4.10),
likelihood ratios, paternity index with mutation (equal model), kinship LR via IBD coefficients, mixture CPI/RMNE,
database search, and an illustrative electropherogram.
"""
from __future__ import annotations

import json
import math
import random
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
CODIS20 = ["D3S1358", "VWA", "D16S539", "CSF1PO", "TPOX", "D8S1179", "D21S11", "D18S51", "D2S441", "D19S433", "TH01", "FGA",
           "D22S1045", "D5S818", "D13S317", "D7S820", "D10S1248", "D1S1656", "D12S391", "D2S1338"]
EXTRA = ["PENTAD", "PENTAE", "SE33"]
KITS = {"CODIS 20 core loci": CODIS20, "CODIS 20 + Penta D/E + SE33": CODIS20 + EXTRA,
        "Original CODIS 13": ["CSF1PO", "FGA", "TH01", "TPOX", "VWA", "D3S1358", "D5S818", "D7S820", "D8S1179", "D13S317",
                              "D16S539", "D18S51", "D21S11"],
        "ESS 12 (European Standard Set)": ["D3S1358", "VWA", "D8S1179", "D21S11", "D18S51", "TH01", "FGA", "D1S1656", "D2S441",
                                           "D10S1248", "D12S391", "D22S1045"]}
# illustrative 5-dye layout (GlobalFiler-like) for the EPG drawing: locus -> (dye, approx. start bp)
EPG_LAYOUT = {"D3S1358": ("blue", 100), "VWA": ("blue", 165), "D16S539": ("blue", 230), "CSF1PO": ("blue", 290), "TPOX": ("blue", 345),
              "D8S1179": ("green", 85), "D21S11": ("green", 180), "D18S51": ("green", 270),
              "D2S441": ("yellow", 75), "D19S433": ("yellow", 130), "TH01": ("yellow", 185), "FGA": ("yellow", 225),
              "D22S1045": ("red", 90), "D5S818": ("red", 135), "D13S317": ("red", 195), "D7S820": ("red", 255), "SE33": ("red", 305),
              "D10S1248": ("purple", 95), "D1S1656": ("purple", 160), "D12S391": ("purple", 220), "D2S1338": ("purple", 290),
              "PENTAD": ("blue", 400), "PENTAE": ("green", 380)}
DYE_COL = {"blue": "#1F77B4", "green": "#2CA02C", "yellow": "#B8860B", "red": "#D62728", "purple": "#8E44AD"}


@lru_cache(maxsize=1)
def DB() -> dict:
    return json.loads((HERE / "str_frequencies.json").read_text())


def populations() -> list[str]:
    return list(DB())


def freq(pop: str, locus: str, allele: str, min_freq: float = .002) -> float:
    d = DB()[pop].get(locus, {})
    a = norm_allele(allele)
    return max(d.get(a, 0.0), min_freq)


def norm_allele(a) -> str:
    s = str(a).strip()
    try:
        f = float(s)
        return str(int(f)) if f == int(f) else str(f)
    except ValueError:
        return s


# ------------------------------------------------------------------ genotype probability / RMP
def genotype_prob(p: float, q: float | None, theta=0.0, method="NRC II 4.1") -> float:
    """Single-locus genotype frequency. q None = homozygote."""
    if q is None:
        if method == "Product rule (HWE)":
            return p * p
        if method == "NRC II 4.1":
            return p * p + p * (1 - p) * theta
        # Balding-Nichols conditional match probability (NRC II 4.10a)
        return ((2 * theta + (1 - theta) * p) * (3 * theta + (1 - theta) * p)) / ((1 + theta) * (1 + 2 * theta))
    if method in ("Product rule (HWE)", "NRC II 4.1"):
        return 2 * p * q
    return 2 * ((theta + (1 - theta) * p) * (theta + (1 - theta) * q)) / ((1 + theta) * (1 + 2 * theta))  # NRC II 4.10b


def parse_genotype(s) -> tuple[str, ...]:
    if s is None or (isinstance(s, float) and math.isnan(s)):
        return ()
    parts = [norm_allele(x) for x in str(s).replace(";", ",").replace("/", ",").replace(" ", ",").split(",") if x.strip()]
    if len(parts) == 1:
        parts = parts * 2
    return tuple(sorted(parts, key=_akey))


def _akey(a):
    try:
        return float(a)
    except ValueError:
        return 999.0


def rmp(profile: dict, pop: str, theta=.01, method="NRC II 4.1", min_freq=.002) -> pd.DataFrame:
    rows = []
    for locus, g in profile.items():
        g = parse_genotype(g)
        if len(g) != 2:
            continue
        a, b = g
        pa = freq(pop, locus, a, min_freq)
        if a == b:
            gp, pb = genotype_prob(pa, None, theta, method), None
        else:
            pb = freq(pop, locus, b, min_freq)
            gp = genotype_prob(pa, pb, theta, method)
        rows.append({"locus": locus, "genotype": f"{a},{b}", "p(a)": pa, "p(b)": pb if pb else pa, "genotype_freq": gp,
                     "1 in": 1 / gp})
    df = pd.DataFrame(rows)
    return df


def combined(df: pd.DataFrame) -> float:
    return float(np.prod(df.genotype_freq)) if len(df) else 1.0


def compare(q: dict, k: dict) -> pd.DataFrame:
    """Compare questioned (crime-scene) vs known (reference) single-source profiles locus by locus."""
    rows = []
    for locus in dict.fromkeys(list(q) + list(k)):
        gq, gk = parse_genotype(q.get(locus)), parse_genotype(k.get(locus))
        if not gq or not gk:
            st = "not typed"
        elif gq == gk:
            st = "match"
        elif set(gq) & set(gk) and (len(set(gq)) == 1 or len(set(gk)) == 1):
            st = "inconclusive (possible drop-out)"
        else:
            st = "EXCLUSION"
        rows.append({"locus": locus, "questioned": ",".join(gq) or "-", "reference": ",".join(gk) or "-", "result": st})
    return pd.DataFrame(rows)


def conclusion(cmp: pd.DataFrame) -> str:
    n_ex = (cmp.result == "EXCLUSION").sum()
    n_m = (cmp.result == "match").sum()
    if n_ex >= 2:
        return "EXCLUDED"
    if n_ex == 1:
        return "INCONCLUSIVE (single-locus difference - possible mutation / artefact; review)"
    n_inc = cmp.result.str.startswith("inconclusive").sum()
    if n_m >= 8:
        return "INCLUDED (cannot be excluded as the source)" + (f" - {n_inc} locus/loci inconclusive" if n_inc else "")
    return "INCONCLUSIVE (insufficient matching loci)"


def verbal(lr: float) -> str:
    """ENFSI verbal equivalents for likelihood ratios."""
    if lr < 1:
        return "supports the alternative proposition"
    scale = [(2, "no support / uninformative"), (10, "weak support"), (100, "moderate support"), (1_000, "moderately strong support"),
             (10_000, "strong support"), (1_000_000, "very strong support")]
    for lim, txt in scale:
        if lr < lim:
            return txt
    return "extremely strong support"


def fmt_big(x: float) -> str:
    if x == 0 or not math.isfinite(x):
        return str(x)
    e = math.floor(math.log10(abs(x)))
    if -3 <= e <= 6:
        return f"{x:,.4g}"
    return f"{x / 10 ** e:.2f} × 10^{e}"


# ------------------------------------------------------------------ paternity / kinship
def _trans(geno: tuple[str, str], allele: str, mu: float, p_a: float) -> float:
    """P(parent transmits `allele`) under the equal mutation model."""
    return sum(.5 * ((1 - mu) * (allele == g) + mu * p_a) for g in geno)


def paternity_locus(child, mother, af, pop, locus, mu=.002, min_freq=.002) -> dict:
    c = parse_genotype(child)
    m = parse_genotype(mother) if mother else ()
    f = parse_genotype(af)
    if len(c) != 2 or len(f) != 2:
        return {"locus": locus, "PI": 1.0, "note": "not typed"}
    pf = lambda a: freq(pop, locus, a, min_freq)  # noqa: E731
    orders = [(c[0], c[1]), (c[1], c[0])] if c[0] != c[1] else [(c[0], c[1])]

    def lik(father_tx):
        tot = 0.0
        for mat, pat in orders:
            pm = _trans(m, mat, mu, pf(mat)) if m else pf(mat)
            tot += pm * father_tx(pat)
        return tot

    h1 = lik(lambda a: _trans(f, a, mu, pf(a)))
    h2 = lik(lambda a: pf(a))
    pi = h1 / h2 if h2 > 0 else float("nan")
    shares = bool(set(c) & set(f))
    note = "consistent" if shares and (not m or any((mat in m and pat in f) for mat, pat in orders)) else "inconsistency (mutation model)"
    return {"locus": locus, "child": ",".join(c), "mother": ",".join(m) or "-", "alleged father": ",".join(f), "PI": pi, "note": note}


IBD = {"Parent-child": (0, 1, 0), "Full siblings": (.25, .5, .25), "Half siblings / grandparent / uncle": (.5, .5, 0),
       "First cousins": (.75, .25, 0), "Unrelated": (1, 0, 0)}


def kinship_locus(g1, g2, pop, locus, rel: str, min_freq=.002) -> float:
    a, b = parse_genotype(g1)
    c, d = parse_genotype(g2)
    pf = lambda x: freq(pop, locus, x, min_freq)  # noqa: E731
    pg2 = pf(c) ** 2 if c == d else 2 * pf(c) * pf(d)

    def given_shared(x):  # P(g2 | g2 carries allele x IBD)
        if x not in (c, d):
            return 0.0
        other = d if x == c else c
        return pf(other) if c != d else pf(c)
    p1 = .5 * given_shared(a) + .5 * given_shared(b)
    p2 = 1.0 if (a, b) == (c, d) else 0.0
    k0, k1, k2 = IBD[rel]
    return (k0 * pg2 + k1 * p1 + k2 * p2) / pg2


# ------------------------------------------------------------------ mixtures
def mixture(alleles_by_locus: dict, pop: str, min_freq=.002) -> pd.DataFrame:
    rows = []
    for locus, al in alleles_by_locus.items():
        al = sorted({norm_allele(x) for x in str(al).replace(";", ",").replace(" ", ",").split(",") if x.strip()}, key=_akey)
        if not al:
            continue
        s = sum(freq(pop, locus, x, min_freq) for x in al)
        rows.append({"locus": locus, "alleles": ",".join(al), "n_alleles": len(al), "sum p": min(s, 1.0),
                     "PI (inclusion)": min(s, 1.0) ** 2})
    return pd.DataFrame(rows)


def poi_included(poi: dict, mix: pd.DataFrame) -> pd.DataFrame:
    out = []
    for r in mix.itertuples():
        g = parse_genotype(poi.get(r.locus))
        al = set(r.alleles.split(","))
        out.append({"locus": r.locus, "POI": ",".join(g) or "-", "mixture": r.alleles,
                    "status": "-" if not g else ("included" if set(g) <= al else "NOT present")})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ simulation / database
def random_profile(pop: str, loci: list[str], rng: random.Random) -> dict:
    prof = {}
    for l in loci:
        d = DB()[pop].get(l)
        if not d:
            continue
        al, w = list(d), list(d.values())
        prof[l] = ",".join(sorted(rng.choices(al, w, k=2), key=_akey))
    return prof


def child_of(m: dict, f: dict, rng: random.Random) -> dict:
    return {l: ",".join(sorted([rng.choice(parse_genotype(m[l])), rng.choice(parse_genotype(f[l]))], key=_akey)) for l in m if l in f}


def make_database(pop: str, n: int, loci: list[str], seed=7) -> pd.DataFrame:
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        p = random_profile(pop, loci, rng)
        p["profile_id"] = f"OFF-{100000 + i}"
        p["category"] = rng.choice(["convicted offender", "arrestee", "forensic unknown", "missing person reference"])
        rows.append(p)
    return pd.DataFrame(rows)


def search(db: pd.DataFrame, query: dict, stringency="moderate", min_loci=8) -> pd.DataFrame:
    loci = [l for l in query if l in db.columns and parse_genotype(query[l])]
    qg = {l: set(parse_genotype(query[l])) for l in loci}
    res = []
    for r in db.itertuples(index=False):
        rd = r._asdict()
        match = partial = mism = 0
        for l in loci:
            g = set(parse_genotype(rd[l]))
            if g == qg[l]:
                match += 1
            elif stringency != "high" and (qg[l] <= g or g <= qg[l]) and len(qg[l]) == 1:
                partial += 1  # query homozygote could be allele drop-out
            elif stringency == "low" and qg[l] & g:
                partial += 1
            else:
                mism += 1
        if mism == 0 and match + partial >= min(min_loci, len(loci)):
            res.append({"profile_id": rd["profile_id"], "category": rd["category"], "loci compared": len(loci), "exact": match,
                        "partial": partial, "candidate": "MATCH" if partial == 0 else "partial candidate"})
    return pd.DataFrame(res)


def epg_traces(profile: dict, peak_height=3000, stutter=.08, imbalance=.15, seed=1):
    """Illustrative electropherogram: one trace per dye with allele + stutter peaks (not instrument data)."""
    rng = np.random.default_rng(seed)
    x = np.linspace(60, 460, 4000)
    traces = {d: np.abs(rng.normal(0, 15, len(x))) for d in DYE_COL}
    labels = []
    for locus, g in profile.items():
        if locus not in EPG_LAYOUT:
            continue
        dye, start = EPG_LAYOUT[locus]
        rep = 5 if locus.startswith("PENTA") else 4
        lo = min((_akey(a) for a in DB()["Europe"].get(locus, {"8": 1})), default=8)
        geno = parse_genotype(g)
        hom = len(geno) == 2 and geno[0] == geno[1]
        for allele in dict.fromkeys(geno):
            n = _akey(allele)
            if n >= 999:
                continue
            pos = start + (n - lo) * rep
            h = peak_height * (2 if hom else 1) * rng.uniform(1 - imbalance, 1 + imbalance)
            traces[dye] += h * np.exp(-((x - pos) ** 2) / (2 * .35 ** 2))
            traces[dye] += h * stutter * np.exp(-((x - (pos - rep)) ** 2) / (2 * .35 ** 2))
            labels.append({"dye": dye, "bp": pos, "height": h, "label": f"{locus}<br>{allele}"})
    return x, traces, labels
