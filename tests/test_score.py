import contextlib
import io
import json
import os
import tempfile
import unittest

import numpy as np

from djbench import cli, score as S
from tests.helpers import write_file


def make_truth(n=40):
    """n synthetic 30 s clips at 100-139 BPM with downbeats; every clip has a key."""
    clips = {}
    keys = ["C major", "A minor", "F# minor", "Bb major"]
    for i in range(n):
        bpm = 100.0 + i
        beats = np.arange(1.0, 30.0, 60.0 / bpm)
        clips[f"clip_{i:03d}"] = {"beats": beats.tolist(), "downbeats": beats[::4].tolist(), "bpm": bpm, "key": keys[i % 4]}
    return {"set": "synthetic", "clips": clips}


def contender(truth, shift=0.0, drop=(), key=None, bpm_scale=1.0, with_down=True):
    out = {}
    for cid, t in truth["clips"].items():
        if cid in drop:
            continue
        e = {"beats": [b + shift for b in t["beats"]], "bpm": t["bpm"] * bpm_scale, "key": key or t["key"]}
        if with_down:
            e["downbeats"] = [b + shift for b in t["downbeats"]]
        out[cid] = e
    return out


class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.truth = make_truth()

    def test_perfect_contender_scores_one_with_zero_width_interval(self):
        r = S.score(self.truth, {"perfect": contender(self.truth)}, n_boot=200)
        for m in ("F@20ms", "F@70ms", "CMLt", "DownF", "Acc1", "KeyExact"):
            v = r["contenders"]["perfect"]["metrics"][m]
            self.assertAlmostEqual(v["mean"], 1.0, places=3, msg=m)
            self.assertAlmostEqual(v["ci"][0], v["ci"][1], places=3)
        self.assertEqual(r["contenders"]["perfect"]["coverage"], [40, 40])

    def test_missing_clips_score_zero_and_coverage_is_reported(self):
        drop = [f"clip_{i:03d}" for i in range(10)]
        r = S.score(self.truth, {"gappy": contender(self.truth, drop=drop)}, n_boot=200)
        c = r["contenders"]["gappy"]
        self.assertEqual(c["coverage"], [30, 40])
        self.assertAlmostEqual(c["metrics"]["F@70ms"]["mean"], 0.75, places=3)           # 30 of 40 clips perfect, 10 miss

    def test_only_common(self):
        drop = [f"clip_{i:03d}" for i in range(10)]
        r = S.score(self.truth, {"a": contender(self.truth), "b": contender(self.truth, drop=drop)}, only_common=True, n_boot=200)
        self.assertEqual(r["clips"], 30)
        self.assertAlmostEqual(r["contenders"]["b"]["metrics"]["F@70ms"]["mean"], 1.0, places=3)

    def test_ranking_and_significance(self):
        c = {"baseline": contender(self.truth, shift=0.0),
             "late": contender(self.truth, shift=0.05),          # 50 ms late: fine at 70 ms, wrong at 20 and 35 ms
             "wrong_tempo": contender(self.truth, bpm_scale=0.5)}
        r = S.score(self.truth, c, n_boot=500)
        pairs = {(p["a"], p["metric"]): p for p in r["pairs"]}
        self.assertGreater(r["contenders"]["late"]["metrics"]["F@70ms"]["mean"], 0.99)    # (a late beat can slip past mir_eval's 5 s trim)
        self.assertEqual(r["contenders"]["late"]["metrics"]["F@20ms"]["mean"], 0.0)
        p = pairs[("late", "F@20ms")]
        self.assertAlmostEqual(p["diff"], -1.0, places=3)
        self.assertLess(p["p"], 1e-6)
        self.assertLessEqual(p["p_holm"], 1.0)
        self.assertLess(abs(pairs[("late", "F@70ms")]["diff"]), 0.01)                      # same, to within the 5 s trim edge
        self.assertEqual(r["contenders"]["wrong_tempo"]["metrics"]["Acc1"]["mean"], 0.0)
        self.assertEqual(r["contenders"]["wrong_tempo"]["metrics"]["Acc2"]["mean"], 1.0)   # half time is an octave error

    def test_metrics_a_contender_never_reports_are_absent_not_zero(self):
        r = S.score(self.truth, {"beats_only": contender(self.truth, with_down=False)}, n_boot=100)
        m = r["contenders"]["beats_only"]["metrics"]
        self.assertNotIn("DownF", m)
        self.assertIn("F@70ms", m)

    def test_include_filter(self):
        r = S.score(self.truth, {"a": contender(self.truth)}, include=r"clip_00\d", n_boot=100)
        self.assertEqual(r["clips"], 10)
        with self.assertRaises(ValueError):
            S.score(self.truth, {"a": contender(self.truth)}, include="nothing_matches", n_boot=100)

    def test_report_text_mentions_everything(self):
        r = S.score(self.truth, {"a": contender(self.truth), "b": contender(self.truth, shift=0.05)}, n_boot=100)
        text = S.format_report(r)
        self.assertIn("synthetic: 40 clips", text)
        self.assertIn("Difference to a", text)
        self.assertIn("F@20ms", text)

    def test_cli_end_to_end(self):
        with tempfile.TemporaryDirectory() as d:
            write_file(os.path.join(d, "truth.json"), json.dumps(self.truth))
            write_file(os.path.join(d, "app_a.json"), json.dumps(contender(self.truth)))
            write_file(os.path.join(d, "app_b.json"), json.dumps(contender(self.truth, shift=0.03)))
            out = os.path.join(d, "res", "out.json")
            with contextlib.redirect_stdout(io.StringIO()):
              cli.main(["score", "--truth", os.path.join(d, "truth.json"), os.path.join(d, "app_a.json"),
                        os.path.join(d, "app_b.json"), "--json", out, "--bootstrap", "100"])
            with open(out) as f:
                res = json.load(f)
        self.assertEqual(set(res["contenders"]), {"app_a", "app_b"})


if __name__ == "__main__":
    unittest.main()
