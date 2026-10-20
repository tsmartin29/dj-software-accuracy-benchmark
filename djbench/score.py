"""Score contenders against a truth file and compare them with confidence intervals and significance tests.

A contender is a JSON file {clip_id: {"beats": [...], "downbeats": [...], "bpm": 124.0, "key": "8A"}} (see adapters/ for converters
from rekordbox, Serato and CSV). The file name (without .json) is the contender's name in the tables.

Rules, so the numbers mean what they say:
  * A clip the contender has no entry for, or an entry with "error", is a MISS: it scores 0 on every metric the contender reports
    elsewhere. Coverage is printed. Use only_common=True to score only the clips every contender produced.
  * The mean of each metric comes with a 95 % percentile-bootstrap interval, resampling clips.
  * The first contender is the baseline. For every other contender: mean difference to the baseline per metric, its paired-bootstrap
    95 % interval, a Wilcoxon signed-rank p-value, and Holm-adjusted p-values across all metrics of that pair.
"""
import json
import math
import os

import numpy as np

from . import metrics as M
from . import stats
from .truth import load_truth, select_clips


def load_contender(path):
    with open(path) as f:
        return json.load(f)


def reports_of(contender):
    ok = [v for v in contender.values() if isinstance(v, dict) and "error" not in v]
    return {"downbeats": any(v.get("downbeats") for v in ok),
            "bpm": any(v.get("bpm") for v in ok),
            "key": any(v.get("key") for v in ok)}


def score(truth, contenders, include=None, ids_file=None, only_common=False, n_boot=10000, seed=0):
    """truth: loaded truth dict. contenders: {name: {clip: entry}}. Returns a result dict (JSON-serialisable)."""
    ids = select_clips(truth["clips"].keys(), include, ids_file)
    if only_common:
        ids = [c for c in ids if all(isinstance(contenders[n].get(c), dict) and "error" not in contenders[n][c] for n in contenders)]
    if not ids:
        raise ValueError("no clips to score (check --include / --ids-file and that clip ids match the truth)")

    per_clip, summary = {}, {}
    for name, cont in contenders.items():
        rep = reports_of(cont)
        rows = [M.clip_metrics(truth["clips"][c], cont.get(c), rep) for c in ids]
        per_clip[name] = {m: np.array([r[m] for r in rows], float) for m in M.ALL_METRICS}
        present = sum(1 for c in ids if isinstance(cont.get(c), dict) and "error" not in cont[c])
        entry = {"coverage": [present, len(ids)], "metrics": {}}
        for m in M.ALL_METRICS:
            mean, lo, hi = stats.bootstrap_ci(per_clip[name][m], n=n_boot, seed=seed)
            if math.isfinite(mean):
                entry["metrics"][m] = {"mean": round(mean, 4), "ci": [round(lo, 4), round(hi, 4)],
                                       "n": int(np.isfinite(per_clip[name][m]).sum())}
        summary[name] = entry

    names = list(contenders)
    pairs = []
    for other in names[1:]:
        rows = []
        for m in M.ALL_METRICS:
            if m in summary[names[0]]["metrics"] and m in summary[other]["metrics"]:
                r = stats.paired_compare(per_clip[other][m], per_clip[names[0]][m], n=n_boot, seed=seed)
                if r["n"]:
                    rows.append((m, r))
        adj = stats.holm([r["p"] for _, r in rows]) if rows else []
        for (m, r), pa in zip(rows, adj):
            pairs.append({"a": other, "b": names[0], "metric": m, "diff": round(r["diff"], 4),
                          "ci": [round(r["lo"], 4), round(r["hi"], 4)], "p": r["p"], "p_holm": pa, "n": r["n"]})
    return {"set": truth.get("set"), "clips": len(ids), "bootstrap": n_boot, "contenders": summary, "pairs": pairs}


def format_report(result):
    """Plain-text tables (also valid to paste in a Markdown code block)."""
    lines = [f"{result['set']}: {result['clips']} clips, {result['bootstrap']} bootstrap resamples (95% CI over clips)"]
    metric_names = [m for m in M.ALL_METRICS if any(m in c["metrics"] for c in result["contenders"].values())]
    for name, c in result["contenders"].items():
        got, total = c["coverage"]
        lines.append(f"\n{name}   (output for {got}/{total} clips; the rest score 0)")
        for m in metric_names:
            if m in c["metrics"]:
                v = c["metrics"][m]
                lines.append(f"  {m:9s} {v['mean']:.3f}  [{v['ci'][0]:.3f}, {v['ci'][1]:.3f}]  n={v['n']}")
    if result["pairs"]:
        names = list(result["contenders"])
        lines.append(f"\nDifference to {names[0]} (positive = better than {names[0]}); paired bootstrap 95% CI, Wilcoxon p, Holm-adjusted p")
        for p in result["pairs"]:
            lines.append(f"  {p['a']:24s} {p['metric']:9s} {p['diff']:+.3f}  [{p['ci'][0]:+.3f}, {p['ci'][1]:+.3f}]  p={p['p']:.3g}  holm={p['p_holm']:.3g}  n={p['n']}")
    return "\n".join(lines)


def run(truth_path, contender_paths, out_json=None, **kw):
    truth = load_truth(truth_path)
    contenders = {os.path.splitext(os.path.basename(p))[0]: load_contender(p) for p in contender_paths}
    result = score(truth, contenders, **kw)
    print(format_report(result))
    if out_json:
        os.makedirs(os.path.dirname(os.path.abspath(out_json)), exist_ok=True)
        with open(out_json, "w") as f:
            json.dump(result, f, indent=1)
    return result
