import unittest
from djbench import keys


class KeyTests(unittest.TestCase):
    def test_note_names(self):
        self.assertEqual(keys.parse_key("F# minor"), (6, "minor"))
        self.assertEqual(keys.parse_key("F#min"), (6, "minor"))
        self.assertEqual(keys.parse_key("Gbm"), (6, "minor"))
        self.assertEqual(keys.parse_key("Bb"), (10, "major"))
        self.assertEqual(keys.parse_key("A major"), (9, "major"))
        self.assertEqual(keys.parse_key("Abmaj"), (8, "major"))
        self.assertEqual(keys.parse_key("Am"), (9, "minor"))

    def test_camelot_and_open_key(self):
        self.assertEqual(keys.parse_key("8A"), (9, "minor"))     # A minor
        self.assertEqual(keys.parse_key("8B"), (0, "major"))     # C major
        self.assertEqual(keys.parse_key("1A"), (8, "minor"))     # G# minor
        self.assertEqual(keys.parse_key("12B"), (4, "major"))    # E major
        self.assertEqual(keys.parse_key("1m"), (9, "minor"))     # Open Key 1m = A minor
        self.assertEqual(keys.parse_key("1d"), (0, "major"))     # Open Key 1d = C major
        self.assertEqual(keys.parse_key("12d"), (5, "major"))    # F major

    def test_camelot_round_trip_all_24(self):
        for pc in range(12):
            for mode in ("major", "minor"):
                self.assertEqual(keys.parse_key(keys.to_camelot((pc, mode))), (pc, mode))

    def test_not_a_key(self):
        for s in ("", None, "No key", "13A", "H minor", "C lydian"):
            self.assertIsNone(keys.parse_key(s), s)

    def test_mirex_scores(self):
        c = keys.parse_key("C major")
        self.assertEqual(keys.key_score(c, keys.parse_key("C major")), 1.0)
        self.assertEqual(keys.key_score(c, keys.parse_key("G major")), 0.5)     # fifth above
        self.assertEqual(keys.key_score(c, keys.parse_key("F major")), 0.5)     # fifth below
        self.assertEqual(keys.key_score(c, keys.parse_key("A minor")), 0.3)     # relative
        self.assertEqual(keys.key_score(c, keys.parse_key("C minor")), 0.2)     # parallel
        self.assertEqual(keys.key_score(c, keys.parse_key("D major")), 0.0)
        self.assertEqual(keys.key_score(c, None), 0.0)
        am = keys.parse_key("A minor")
        self.assertEqual(keys.key_score(am, keys.parse_key("C major")), 0.3)    # relative, the other way
        self.assertEqual(keys.key_score(am, keys.parse_key("E minor")), 0.5)

    def test_mix_compatible(self):
        c = keys.parse_key("C major")
        for s, want in (("C major", 1.0), ("G major", 1.0), ("A minor", 1.0), ("C minor", 0.0), ("D major", 0.0)):
            self.assertEqual(keys.key_mix_compatible(c, keys.parse_key(s)), want, s)


if __name__ == "__main__":
    unittest.main()
