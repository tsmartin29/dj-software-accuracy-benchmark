"""Confidence intervals and significance tests over clips.

The unit of resampling is the CLIP (a track), never the individual beat: beats inside one track are not independent.
"""
import numpy as np
from scipy.stats import wilcoxon


def bootstrap_ci(x, n=10000, seed=0, level=0.95):
    """Percentile bootstrap CI of the mean of x (NaNs dropped). Returns (mean, lo, hi); (nan, nan, nan) for an empty input."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if len(x) == 0:
        return float("nan"), float("nan"), float("nan")
    if len(x) == 1:
        return float(x[0]), float(x[0]), float(x[0])
    rng = np.random.default_rng(seed)
    means = np.empty(n)
    chunk = max(1, 2_000_000 // len(x))                  # keep memory flat for big sets
    for i in range(0, n, chunk):
        k = min(chunk, n - i)
        means[i:i + k] = x[rng.integers(0, len(x), (k, len(x)))].mean(axis=1)
    a = (1 - level) / 2
    return float(x.mean()), float(np.percentile(means, 100 * a)), float(np.percentile(means, 100 * (1 - a)))


def paired_compare(a, b, n=10000, seed=0):
    """Paired comparison of two contenders on the same clips (a minus b).

    Returns dict(diff, lo, hi, p, n): mean difference, its 95 % paired-bootstrap interval, the Wilcoxon signed-rank p-value
    (two-sided; clips where both are equal are ignored by the test, p = 1 if every clip is equal) and the number of clips used.
    Clips where either value is NaN are dropped."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    ok = np.isfinite(a) & np.isfinite(b)
    d = (a - b)[ok]
    if len(d) == 0:
        return dict(diff=float("nan"), lo=float("nan"), hi=float("nan"), p=float("nan"), n=0)
    mean, lo, hi = bootstrap_ci(d, n=n, seed=seed)
    p = 1.0
    if np.any(d != 0):
        try:
            p = float(wilcoxon(d).pvalue)
        except ValueError:
            p = 1.0
    return dict(diff=mean, lo=lo, hi=hi, p=p, n=int(len(d)))


def holm(pvalues):
    """Holm-Bonferroni adjusted p-values (same order as the input). Use it when you read many metrics/pairs at once."""
    p = np.asarray(pvalues, float)
    order = np.argsort(p)
    m = len(p)
    adj = np.empty(m)
    running = 0.0
    for rank, idx in enumerate(order):
        running = max(running, (m - rank) * p[idx])
        adj[idx] = min(1.0, running)
    return adj.tolist()
