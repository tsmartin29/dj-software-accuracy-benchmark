import math
import unittest
import numpy as np
from djbench import stats


class BootstrapTests(unittest.TestCase):
    def test_constant_has_zero_width(self):
        m, lo, hi = stats.bootstrap_ci([0.7] * 40)
        self.assertEqual((m, lo, hi), (0.7, 0.7, 0.7))

    def test_known_interval_for_fifty_fifty(self):
        x = [0.0] * 50 + [1.0] * 50                      # mean .5, standard error .05 -> 95 % interval about +/- .098
        m, lo, hi = stats.bootstrap_ci(x, n=5000, seed=3)
        self.assertEqual(m, 0.5)
        self.assertTrue(0.38 < lo < 0.43, lo)
        self.assertTrue(0.57 < hi < 0.62, hi)

    def test_interval_shrinks_with_more_clips(self):
        rng = np.random.default_rng(0)
        small = stats.bootstrap_ci(rng.random(30), n=3000)
        large = stats.bootstrap_ci(rng.random(3000), n=3000)
        self.assertGreater(small[2] - small[1], 3 * (large[2] - large[1]))

    def test_deterministic_for_a_seed(self):
        x = np.random.default_rng(1).random(50)
        self.assertEqual(stats.bootstrap_ci(x, seed=5), stats.bootstrap_ci(x, seed=5))

    def test_nan_dropped_and_empty(self):
        self.assertEqual(stats.bootstrap_ci([1.0, float("nan"), 1.0])[0], 1.0)
        self.assertTrue(math.isnan(stats.bootstrap_ci([float("nan")])[0]))


class PairedTests(unittest.TestCase):
    def test_identical_is_not_significant(self):
        x = np.random.default_rng(2).random(60)
        r = stats.paired_compare(x, x)
        self.assertEqual((r["diff"], r["p"]), (0.0, 1.0))

    def test_consistent_gain_is_significant(self):
        rng = np.random.default_rng(3)
        b = rng.random(80) * 0.8
        a = b + 0.1 + rng.normal(0, 0.02, 80)
        r = stats.paired_compare(a, b)
        self.assertAlmostEqual(r["diff"], 0.1, delta=0.01)
        self.assertGreater(r["lo"], 0.08)
        self.assertLess(r["p"], 1e-6)

    def test_noise_is_not_significant(self):
        rng = np.random.default_rng(4)
        a, b = rng.random(80), rng.random(80)
        r = stats.paired_compare(a, b)
        self.assertLess(r["lo"], 0.0)
        self.assertGreater(r["hi"], 0.0)
        self.assertGreater(r["p"], 0.05)

    def test_nan_pairs_dropped(self):
        a = [1.0, float("nan")] + [0.5 + 0.01 * i for i in range(10)]
        b = [0.0, 1.0] + [0.4 + 0.012 * i for i in range(10)]
        r = stats.paired_compare(a, b)
        self.assertEqual(r["n"], 11)


class HolmTests(unittest.TestCase):
    def test_known_answer(self):
        self.assertEqual([round(p, 6) for p in stats.holm([0.01, 0.04, 0.03])], [0.03, 0.06, 0.06])

    def test_capped_at_one(self):
        self.assertEqual(stats.holm([0.6, 0.7]), [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
