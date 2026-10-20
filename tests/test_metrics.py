import math
import unittest
import numpy as np
from djbench import metrics as M


REF = np.arange(1.0, 31.0, 0.5)          # 120 BPM, 30 s; 52 beats survive mir_eval's 5 s trim


class BeatMetricTests(unittest.TestCase):
    def test_perfect(self):
        r = M.beat_metrics(REF, REF)
        for k in ("F@20ms", "F@35ms", "F@70ms", "CMLt", "AMLt"):
            self.assertAlmostEqual(r[k], 1.0, places=6, msg=k)

    def test_constant_offset_windows(self):
        r = M.beat_metrics(REF, REF + 0.05)          # 50 ms late: inside 70 ms, outside 35 and 20
        self.assertEqual(r["F@70ms"], 1.0)
        self.assertEqual(r["F@35ms"], 0.0)
        self.assertEqual(r["F@20ms"], 0.0)
        r = M.beat_metrics(REF, REF - 0.03)          # 30 ms early: inside 35, outside 20
        self.assertGreater(r["F@35ms"], 0.98)        # (not exactly 1: the beat at 4.97 s falls into the trimmed 5 s, its partner does not)
        self.assertEqual(r["F@20ms"], 0.0)

    def test_half_tempo(self):
        est = np.arange(1.0, 31.0, 1.0)              # every other beat: precision 1, recall 0.5 -> F = 2/3
        r = M.beat_metrics(REF, est)
        self.assertAlmostEqual(r["F@70ms"], 2 / 3, places=6)
        self.assertLess(r["CMLt"], 0.1)              # not the correct metric level
        self.assertGreater(r["AMLt"], 0.9)           # but a legal one (half time)

    def test_off_beat(self):
        r = M.beat_metrics(REF, REF + 0.25)          # exactly on the off-beats
        self.assertEqual(r["F@70ms"], 0.0)
        self.assertGreater(r["AMLt"], 0.9)

    def test_empty_or_tiny_estimate_is_zero(self):
        for est in ([], [3.0], None):
            r = M.beat_metrics(REF, est)
            self.assertEqual(set(r.values()), {0.0})

    def test_unsorted_duplicate_negative_input_is_cleaned(self):
        est = np.concatenate([REF[::-1], REF[:5], [-3.0, float("nan")]])
        self.assertAlmostEqual(M.beat_metrics(REF, est)["F@70ms"], 1.0, places=6)

    def test_first_five_seconds_are_ignored(self):
        est = REF[REF >= 5.0]                        # nothing before 5 s: still perfect
        self.assertAlmostEqual(M.beat_metrics(REF, est)["F@70ms"], 1.0, places=6)


class DownbeatTests(unittest.TestCase):
    def test_downbeat_f(self):
        ref = np.arange(1.0, 31.0, 2.0)
        self.assertEqual(M.downbeat_f(ref, ref), 1.0)
        self.assertEqual(M.downbeat_f(ref, ref + 0.5), 0.0)          # beat 2 called beat 1
        self.assertEqual(M.downbeat_f(ref, []), 0.0)
        self.assertTrue(math.isnan(M.downbeat_f([], ref)))           # no truth downbeats: not scored

    def test_downbeats_are_not_trimmed(self):
        ref = np.array([1.0, 3.0, 5.0, 7.0])
        self.assertEqual(M.downbeat_f(ref, ref), 1.0)


class TempoTests(unittest.TestCase):
    def test_acc1_acc2(self):
        self.assertEqual(M.tempo_metrics(124.0, 124.5), {"Acc1": 1.0, "Acc2": 1.0})
        self.assertEqual(M.tempo_metrics(128.0, 64.0), {"Acc1": 0.0, "Acc2": 1.0})       # half time
        self.assertEqual(M.tempo_metrics(60.0, 180.0), {"Acc1": 0.0, "Acc2": 1.0})       # triple
        self.assertEqual(M.tempo_metrics(120.0, 90.0), {"Acc1": 0.0, "Acc2": 0.0})       # 3/4 is not an octave error
        self.assertEqual(M.tempo_metrics(100.0, 104.0)["Acc1"], 1.0)                     # exactly 4 %
        self.assertEqual(M.tempo_metrics(100.0, 104.5)["Acc1"], 0.0)

    def test_missing(self):
        self.assertEqual(M.tempo_metrics(120.0, None), {"Acc1": 0.0, "Acc2": 0.0})
        self.assertTrue(math.isnan(M.tempo_metrics(None, 120.0)["Acc1"]))

    def test_tempo_from_beats(self):
        self.assertAlmostEqual(M.tempo_from_beats(np.arange(0, 20, 0.5)), 120.0)
        self.assertTrue(math.isnan(M.tempo_from_beats([1.0, 2.0])))


class KeyMetricTests(unittest.TestCase):
    def test_key_metrics(self):
        self.assertEqual(M.key_metrics("C major", "8B"), {"KeyScore": 1.0, "KeyExact": 1.0, "KeyMix": 1.0})
        self.assertEqual(M.key_metrics("C major", "Am"), {"KeyScore": 0.3, "KeyExact": 0.0, "KeyMix": 1.0})
        self.assertEqual(M.key_metrics("C major", "C minor"), {"KeyScore": 0.2, "KeyExact": 0.0, "KeyMix": 0.0})
        self.assertEqual(M.key_metrics("C major", "garbage"), {"KeyScore": 0.0, "KeyExact": 0.0, "KeyMix": 0.0})
        self.assertTrue(math.isnan(M.key_metrics("???", "C major")["KeyScore"]))


class ClipMetricsTests(unittest.TestCase):
    TRUTH = {"beats": REF.tolist(), "downbeats": REF[::4].tolist(), "bpm": 120.0, "key": "C major"}

    def test_full_entry(self):
        est = {"beats": REF.tolist(), "downbeats": REF[::4].tolist(), "bpm": 120.0, "key": "8B"}
        r = M.clip_metrics(self.TRUTH, est, {"downbeats": True, "bpm": True, "key": True})
        for m in M.ALL_METRICS:
            self.assertAlmostEqual(r[m], 1.0, places=6, msg=m)

    def test_error_entry_is_a_miss(self):
        r = M.clip_metrics(self.TRUTH, {"error": "not analysed"}, {"downbeats": True, "bpm": True, "key": True})
        for m in M.ALL_METRICS:
            self.assertEqual(r[m], 0.0, m)

    def test_fields_never_reported_are_nan_not_zero(self):
        est = {"beats": REF.tolist()}
        r = M.clip_metrics(self.TRUTH, est, {"downbeats": False, "bpm": False, "key": False})
        self.assertAlmostEqual(r["F@70ms"], 1.0, places=6)
        for m in ("DownF", "Acc1", "Acc2", "KeyScore"):
            self.assertTrue(math.isnan(r[m]), m)

    def test_tempo_derived_from_truth_beats_when_no_bpm(self):
        truth = {"beats": REF.tolist()}
        r = M.clip_metrics(truth, {"beats": REF.tolist(), "bpm": 121.0}, {"bpm": True})
        self.assertEqual(r["Acc1"], 1.0)


if __name__ == "__main__":
    unittest.main()
