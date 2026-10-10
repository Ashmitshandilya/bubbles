"""Honest association analysis for personal health logs. Pure Python, deterministic, no database.

What it does: pairs two logged series by date (missing is never zero), measures a rank correlation (Spearman) with an
effect size and a permutation p-value, corrects for many comparisons (Benjamini-Hochberg), and only calls something a
"candidate_association" when there is enough data, a meaningful effect and q below the threshold. A "repeated_pattern"
additionally needs the same direction in both chronological halves. Everything else is reported as
insufficient_data / no_pattern. It never states causation.

Thresholds are [BUBBLES] defaults that need statistical + clinical review before they gate user-facing insights.
Add a relationship: build the two date-keyed series, call analyze_batch([...]); show only findings whose status is
candidate_association or repeated_pattern, with their `limitations`.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

MIN_PAIRS = 10          # complete (x, y) pairs required before any association is reported
MIN_EFFECT = 0.30       # |Spearman rho| below this is "too small to matter" even if "significant"
Q_MAX = 0.10            # false-discovery rate across the batch of comparisons examined
MIN_HALF = 6            # pairs needed in each half to check that the pattern repeats
HALF_EFFECT = 0.20      # |rho| needed in each half, same sign as overall
PERMUTATIONS = 2000
EARLY_STOP = 200        # after this many shuffles a pair that already looks null (p > ~0.5) is not shuffled further
VERSION = "1.0"
NOT_CAUSAL = "An association in your own logs; it does not show that one thing causes the other."
CONFOUNDERS = "Other things that changed on the same days (illness, stress, travel, cycle phase, medication) are not accounted for."


@dataclass
class Finding:
    label: str
    status: str                     # insufficient_data | no_pattern | candidate_association | repeated_pattern
    n: int = 0
    rho: float | None = None
    p: float | None = None
    q: float | None = None
    repeated: bool | None = None
    reason: str = ""
    limitations: list[str] = field(default_factory=list)
    version: str = VERSION

    def to_dict(self) -> dict:
        return asdict(self)


def _ranks(v: list[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    r = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            r[order[k]] = avg
        i = j + 1
    return r


def _pearson(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    ma, mb = sum(a) / n, sum(b) / n
    sa = sum((x - ma) ** 2 for x in a)
    sb = sum((y - mb) ** 2 for y in b)
    if sa == 0 or sb == 0:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (sa * sb) ** 0.5


def spearman(x: list[float], y: list[float]) -> float | None:
    return _pearson(_ranks(x), _ranks(y))


def perm_p(x: list[float], y: list[float], rho: float, seed: int = 20261009) -> float:
    """Two-sided permutation p-value (deterministic)."""
    rng = random.Random(seed)
    rx, ry = _ranks(x), _ranks(y)
    hits = 0
    for i in range(PERMUTATIONS):
        rng.shuffle(ry)
        r = _pearson(rx, ry)
        if r is not None and abs(r) >= abs(rho) - 1e-12:
            hits += 1
        if i == EARLY_STOP - 1 and hits * 2 >= EARLY_STOP:   # clearly null (p > ~0.5): the exact value cannot change a verdict
            return (hits + 1) / (EARLY_STOP + 1)
    return (hits + 1) / (PERMUTATIONS + 1)


def benjamini_hochberg(pvals: list[float]) -> list[float]:
    """BH-adjusted q-values, same order as the input."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    q = [0.0] * m
    prev = 1.0
    for rank in range(m, 0, -1):
        i = order[rank - 1]
        prev = min(prev, pvals[i] * m / rank)
        q[i] = prev
    return q


def paired(sx: dict[date, float | None], sy: dict[date, float | None], lag_days: int = 0) -> list[tuple[float, float]]:
    """Pairs sx[d] with sy[d + lag] for days where BOTH were logged, oldest first. Missing is never zero."""
    out = []
    for d in sorted(sx):
        a, b = sx.get(d), sy.get(d + timedelta(days=lag_days))
        if a is None or b is None:
            continue
        try:
            out.append((float(a), float(b)))
        except (TypeError, ValueError):
            continue
    return out


def dedupe_events(days: list[date], min_gap_days: int = 2) -> list[date]:
    """Collapse one episode that was logged on several consecutive days into a single event."""
    out: list[date] = []
    for d in sorted(set(days)):
        if not out or (d - out[-1]).days > min_gap_days:
            out.append(d)
    return out


def assess_pairs(label: str, pairs: list[tuple[float, float]]) -> Finding:
    """Stage 1 (before multiple-comparison correction): effect size and permutation p."""
    n = len(pairs)
    if n < MIN_PAIRS:
        return Finding(label, "insufficient_data", n, reason=f"needs at least {MIN_PAIRS} days where both were logged (have {n})")
    x, y = [p[0] for p in pairs], [p[1] for p in pairs]
    rho = spearman(x, y)
    if rho is None:
        return Finding(label, "insufficient_data", n, reason="one of the series did not vary, so no relationship can be measured")
    f = Finding(label, "no_pattern", n, round(rho, 3), round(perm_p(x, y, rho), 4), limitations=[NOT_CAUSAL, CONFOUNDERS])
    h = n // 2
    if h >= MIN_HALF and n - h >= MIN_HALF:
        r1, r2 = spearman(x[:h], y[:h]), spearman(x[h:], y[h:])
        f.repeated = bool(r1 is not None and r2 is not None and r1 * rho > 0 and r2 * rho > 0 and min(abs(r1), abs(r2)) >= HALF_EFFECT)
    return f


def analyze_batch(specs: list[tuple[str, list[tuple[float, float]]]]) -> list[Finding]:
    """Assess every candidate relationship, adjust for how many were examined, and classify.
    Examining 40 pairs and reporting the best 2 is exactly the failure this guards against."""
    findings = [assess_pairs(label, pairs) for label, pairs in specs]
    testable = [f for f in findings if f.p is not None]
    for f, q in zip(testable, benjamini_hochberg([f.p for f in testable])):
        f.q = round(q, 4)
        if f.q <= Q_MAX and abs(f.rho) >= MIN_EFFECT:
            f.status = "repeated_pattern" if f.repeated else "candidate_association"
            if not f.repeated:
                f.limitations.append("Not yet seen repeating across two separate periods of your logs.")
        else:
            f.reason = "no reliable relationship found" if f.q > Q_MAX else "relationship too small to matter"
    return findings
