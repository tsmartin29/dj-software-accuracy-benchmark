import io
import os
import struct
import tarfile
import tempfile
import unittest
import wave

from djbench import datasets as D, truth as T
from tests.helpers import write_file


def make_au(samples, rate=22050):
    pcm = b"".join(struct.pack(">h", s) for s in samples)
    return b".snd" + struct.pack(">5I", 24, len(pcm), 3, rate, 1) + pcm


class TruthParsingTests(unittest.TestCase):
    def test_beats_file_with_numbers(self):
        beats, down = T.parse_beats_file("0.217\t3\n0.695\t4\n1.173\t1\n1.653\t2\n2.131\t3\n2.609\t4\n3.087\t1\n")
        self.assertEqual(len(beats), 7)
        self.assertEqual(down, [1.173, 3.087])

    def test_beats_file_without_numbers(self):
        beats, down = T.parse_beats_file("0.6775\n1.9346\n3.1265\n\n")
        self.assertEqual(beats, [0.6775, 1.9346, 3.1265])
        self.assertIsNone(down)

    def test_convert_annotation_folder(self):
        with tempfile.TemporaryDirectory() as d:
            b = os.path.join(d, "toyset", "annotations", "beats")
            os.makedirs(b)
            write_file(os.path.join(b, "toy_001.beats"), "0.5\t1\n1.0\t2\n1.5\t1\n")
            write_file(os.path.join(b, "ignored.txt"), "x")
            out = os.path.join(d, "truth", "toyset.json")
            self.assertEqual(T.convert_beat_annotations(os.path.join(d, "toyset"), out), 1)
            t = T.load_truth(out)
        self.assertEqual(t["set"], "toyset")
        self.assertEqual(t["clips"]["toy_001"], {"beats": [0.5, 1.0, 1.5], "downbeats": [0.5, 1.5]})

    def test_select_clips(self):
        ids = ["gtzan_disco_00001", "gtzan_pop_00002", "gtzan_rock_00003"]
        self.assertEqual(T.select_clips(ids, include="disco|pop"), ids[:2])


class Gtzan(unittest.TestCase):
    def test_clip_ids(self):
        self.assertEqual(D.gtzan_clip_id("genres/blues/blues.00012.au"), "gtzan_blues_00012")
        self.assertEqual(D.gtzan_clip_id("genres/hiphop/hiphop.00099.au"), "gtzan_hiphop_00099")
        self.assertIsNone(D.gtzan_clip_id("genres/blues/._blues.00012.au".replace("._", "")+".txt"))
        self.assertIsNone(D.gtzan_clip_id("genres/blues/readme"))

    def test_au_reader_converts_endianness(self):
        rate, ch, pcm = D.read_au(make_au([0, 1, -1, 1000, -32768, 32767]))
        self.assertEqual((rate, ch), (22050, 1))
        self.assertEqual(struct.unpack("<6h", pcm), (0, 1, -1, 1000, -32768, 32767))

    def test_au_reader_rejects_other_formats(self):
        with self.assertRaises(ValueError):
            D.read_au(b"RIFF" + b"\x00" * 40)
        with self.assertRaises(ValueError):
            D.read_au(b".snd" + struct.pack(">5I", 24, 4, 1, 22050, 1) + b"\x00" * 4)         # mu-law

    def test_prepare_from_a_synthetic_tarball(self):
        with tempfile.TemporaryDirectory() as d:
            tar = os.path.join(d, "genres.tar.gz")
            with tarfile.open(tar, "w:gz") as tf:
                for name, data in (("genres/disco/disco.00000.au", make_au([1, 2, 3, 4])),
                                   ("genres/pop/pop.00007.au", make_au([5, 6])),
                                   ("genres/jazz/jazz.00054.au", b"corrupt"),
                                   ("../evil/evil.00001.au", make_au([9])),
                                   ("genres/notes.txt", b"hi")):
                    ti = tarfile.TarInfo(name)
                    ti.size = len(data)
                    tf.addfile(ti, io.BytesIO(data))
            out = os.path.join(d, "audio")
            D.prepare_gtzan(tar, out)
            self.assertEqual(sorted(os.listdir(out)), ["gtzan_disco_00000.wav", "gtzan_pop_00007.wav"])
            with wave.open(os.path.join(out, "gtzan_disco_00000.wav")) as w:
                self.assertEqual((w.getnchannels(), w.getsampwidth(), w.getframerate(), w.getnframes()), (1, 2, 22050, 4))
                self.assertEqual(struct.unpack("<4h", w.readframes(4)), (1, 2, 3, 4))

    def test_unsafe_members_are_refused(self):
        self.assertFalse(D.safe_member("../x"))
        self.assertFalse(D.safe_member("/etc/passwd"))
        self.assertTrue(D.safe_member("genres/a/a.00001.au"))


class GiantSteps(unittest.TestCase):
    def test_truth_from_repo_layout(self):
        with tempfile.TemporaryDirectory() as d:
            for sub in ("annotations_v2/tempo", "annotations/tempo", "annotations/key"):
                os.makedirs(os.path.join(d, sub))
            write_file(os.path.join(d, "annotations_v2/tempo/1000001.LOFI.bpm"), "127.0\n")
            write_file(os.path.join(d, "annotations_v2/tempo/1000002.LOFI.bpm"), "0.0\n")        # unlabeled in v2
            write_file(os.path.join(d, "annotations/tempo/1000001.LOFI.bpm"), "128.0\n")
            write_file(os.path.join(d, "annotations/key/1000003.LOFI.key"), "F# minor\n")
            out = os.path.join(d, "truth")
            v2 = D.build_giantsteps_truth(d, "tempo", out, "v2")
            v1 = D.build_giantsteps_truth(d, "tempo", out, "v1")
            key = D.build_giantsteps_truth(d, "key", out)
        self.assertEqual(v2, {"gs_1000001": {"bpm": 127.0}})
        self.assertEqual(v1, {"gs_1000001": {"bpm": 128.0}})
        self.assertEqual(key, {"gs_1000003": {"key": "F# minor"}})


if __name__ == "__main__":
    unittest.main()
