"""Per-clip metrics: beats (F-measure at several windows, continuity), downbeats, tempo and key.

Beat metrics are mir_eval's (https://github.com/mir-evaluation/mir_eval, Raffel et al., ISMIR 2014). As in the beat-tracking literature
mir_eval drops beats in the first 5 seconds of both reference and estimate before comparing (trim_beats); downbeats are NOT trimmed.

Names used in the output:
    F@20ms F@35ms F@70ms   beat F-measure with a +/- window around each reference beat (70 ms is the usual literature value; the
                           tighter windows matter for DJ work, where a grid 40 ms off is audibly flamming)
    CMLt AMLt              continuity: share of the track that is on the correct beat level / on any metric level (mir_eval)
    DownF                  downbeat F-measure at +/- 70 ms (only when both sides have downbeats)
    Acc1 Acc2              tempo within 4 % of the reference / the same, also accepting 2x, 1/2, 3x, 1/3 (Gouyon et al. 2006)
    KeyScore KeyExact KeyMix   MIREX weighted key score / exact match / "mixes harmonically" (exact, fifth neighbour or relative)

A metric that does not apply to a clip (the contender reports no downbeats at all, the truth has no tempo) is NaN, not 0.
"""
import math
import numpy as np
import mir_eval

from . import keys

BEAT_WINDOWS_MS = (20, 35, 70)
BEAT_METRICS = ["F@20ms", "F@35ms", "F@70ms", "CMLt", "AMLt"]
DOWN_METRICS = ["DownF"]
TEMPO_METRICS = ["Acc1", "Acc2"]
KEY_METRICS = ["KeyScore", "KeyExact", "KeyMix"]
ALL_METRICS = BEAT_METRICS + DOWN_METRICS + TEMPO_METRICS + KEY_METRICS


def clean_times(x):
    """Sorted, finite, non-negative float array (mir_eval insists on this)."""
    a = np.asarray(x if x is not None else [], dtype=float).ravel()
    a = a[np.isfinite(a) & (a >= 0)]
    return np.unique(a)                       # sorted and de-duplicated


def beat_metrics(ref, est, windows_ms=BEAT_WINDOWS_MS):
    """Beat metrics for one clip. ref and est are arrays of beat times in seconds. Empty estimate -> all zeros."""
    out = {f"F@{w}ms": 0.0 for w in windows_ms}
    out.update(CMLt=0.0, AMLt=0.0)
    r, e = mir_eval.beat.trim_beats(clean_times(ref)), mir_eval.beat.trim_beats(clean_times(est))
    if len(r) < 2 or len(e) < 2:
        return out
    for w in windows_ms:
        out[f"F@{w}ms"] = float(mir_eval.beat.f_measure(r, e, f_measure_threshold=w / 1000.0))
    _, cml_t, _, aml_t = mir_eval.beat.continuity(r, e)
    out["CMLt"], out["AMLt"] = float(cml_t), float(aml_t)
    return out


def downbeat_f(ref_down, est_down, window_ms=70):
    r, e = clean_times(ref_down), clean_times(est_down)
    if len(r) == 0:
        return float("nan")
    if len(e) == 0:
        return 0.0
    return float(mir_eval.beat.f_measure(r, e, f_measure_threshold=window_ms / 1000.0))


def tempo_from_beats(beats):
    """Median-inter-beat-interval tempo in BPM (used when a truth file has beats but no tempo). NaN with fewer than 3 beats."""
    b = clean_times(beats)
    if len(b) < 3:
        return float("nan")
    return float(60.0 / np.median(np.diff(b)))


def tempo_metrics(ref_bpm, est_bpm, tol=0.04):
    """Acc1 / Acc2 (see module doc). est_bpm None or <= 0 counts as a miss; ref_bpm NaN/None -> NaN."""
    if ref_bpm is None or not math.isfinite(ref_bpm) or ref_bpm <= 0:
        return {"Acc1": float("nan"), "Acc2": float("nan")}
    if est_bpm is None or not math.isfinite(est_bpm) or est_bpm <= 0:
        return {"Acc1": 0.0, "Acc2": 0.0}
    within = lambda t: abs(est_bpm - t) <= tol * t
    acc1 = within(ref_bpm)
    acc2 = acc1 or any(within(ref_bpm * f) for f in (2.0, 0.5, 3.0, 1.0 / 3.0))
    return {"Acc1": float(acc1), "Acc2": float(acc2)}


def key_metrics(ref_key, est_key):
    """ref_key / est_key: strings in any form keys.parse_key understands. Unparsable estimate scores 0; unparsable reference NaN."""
    ref = keys.parse_key(ref_key)
    if ref is None:
        return {m: float("nan") for m in KEY_METRICS}
    est = keys.parse_key(est_key)
    score = keys.key_score(ref, est)
    return {"KeyScore": score, "KeyExact": float(score == 1.0), "KeyMix": keys.key_mix_compatible(ref, est)}


def clip_metrics(truth, est, reports):
    """All metrics for one clip.

    truth:   dict with any of beats, downbeats, bpm, key
    est:     the contender's dict for this clip, or None / {"error": ...} (a miss: scores 0 where the truth has something to score)
    reports: which fields this contender ever reports ({"downbeats": bool, "bpm": bool, "key": bool}); a field it never reports is NaN
    """
    ok = bool(est) and "error" not in est
    est = est if ok else {}
    out = {m: float("nan") for m in ALL_METRICS}
    if truth.get("beats") is not None and len(truth["beats"]) >= 2:
        out.update(beat_metrics(truth["beats"], est.get("beats")))
        if truth.get("downbeats") and reports.get("downbeats"):
            out["DownF"] = downbeat_f(truth["downbeats"], est.get("downbeats")) if ok else 0.0
    ref_bpm = truth.get("bpm")
    if ref_bpm is None and truth.get("beats") is not None:
        ref_bpm = tempo_from_beats(truth["beats"])
    if ref_bpm is not None and reports.get("bpm"):
        out.update(tempo_metrics(ref_bpm, est.get("bpm")))
    if truth.get("key") and reports.get("key"):
        out.update(key_metrics(truth["key"], est.get("key")))
    return out
