import os
import struct
import sys
import tempfile
import types
import unittest

from tests.helpers import write_file
from djbench.adapters import expand_grid, generic, rekordbox_anlz, rekordbox_xml, serato


class ExpandGridTests(unittest.TestCase):
    def test_constant_grid(self):
        beats, downs, _ = expand_grid([(0.5, 120.0, 1)], 4.0)
        self.assertEqual(beats[:4], [0.5, 1.0, 1.5, 2.0])
        self.assertEqual(downs, [0.5, 2.5])                        # every 4th beat, first marker is a bar start
        self.assertAlmostEqual(beats[-1], 4.0)

    def test_marker_on_beat_three(self):
        _, downs, _ = expand_grid([(0.0, 120.0, 3)], 4.0)          # beat 3 at t=0 -> beat 1 two beats later (1.0 s)
        self.assertEqual(downs, [1.0, 3.0])

    def test_tempo_change(self):
        beats, _, bpms = expand_grid([(0.0, 120.0, 1), (2.0, 60.0, 1)], 5.0)
        self.assertEqual(beats, [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0])
        self.assertEqual(bpms[0], 120.0)
        self.assertEqual(bpms[-1], 60.0)


class GenericTests(unittest.TestCase):
    def test_csv(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.csv")
            with open(p, "w") as f:
                f.write("clip,time,beat_in_bar,bpm,key\n"
                        "a,0.5,1,124.0,8A\na,1.0,2,,\na,1.5,3,,\na,2.0,4,,\na,2.5,1,,\n"
                        "b,0.4,,,\nb,0.9,,,\n"
                        "c,,,100,Am\n")
            out = generic.read_csv(p)
        self.assertEqual(out["a"]["beats"], [0.5, 1.0, 1.5, 2.0, 2.5])
        self.assertEqual(out["a"]["downbeats"], [0.5, 2.5])
        self.assertEqual((out["a"]["bpm"], out["a"]["key"]), (124.0, "8A"))
        self.assertEqual(out["b"]["beats"], [0.4, 0.9])
        self.assertNotIn("downbeats", out["b"])
        self.assertEqual(out["c"]["beats"], [])
        self.assertEqual(out["c"]["key"], "Am")


XML = """<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0"><COLLECTION Entries="3">
 <TRACK TrackID="1" Name="synthetic one" Location="file://localhost/Music/Bench/clip%20one.wav" TotalTime="10" AverageBpm="120.00" Tonality="Am">
  <TEMPO Inizio="0.250" Bpm="120.00" Metro="4/4" Battito="1"/>
 </TRACK>
 <TRACK TrackID="2" Name="synthetic two" Location="file://localhost/Music/Bench/clip_two.wav" TotalTime="6" AverageBpm="90.00" Tonality="8B">
  <TEMPO Inizio="0.000" Bpm="120.00" Metro="4/4" Battito="1"/>
  <TEMPO Inizio="2.000" Bpm="60.00" Metro="4/4" Battito="1"/>
 </TRACK>
 <TRACK TrackID="3" Name="not analysed" Location="file://localhost/Music/Other/clip_three.wav" TotalTime="6"/>
</COLLECTION></DJ_PLAYLISTS>
"""


class RekordboxXmlTests(unittest.TestCase):
    def _read(self, **kw):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "rb.xml")
            write_file(p, XML)
            return rekordbox_xml.read(p, **kw)

    def test_constant_and_changing_grid(self):
        out = self._read()
        one = out["clip one"]                                       # %20 decoded, extension removed
        self.assertEqual(one["beats"][:3], [0.25, 0.75, 1.25])
        self.assertEqual(one["downbeats"][:2], [0.25, 2.25])
        self.assertEqual((one["bpm"], one["key"]), (120.0, "Am"))
        two = out["clip_two"]
        self.assertEqual(two["beats"], [0.0, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0])
        self.assertEqual(two["key"], "8B")

    def test_untracked_is_an_error_entry(self):
        self.assertIn("error", self._read()["clip_three"])

    def test_folder_filter(self):
        out = self._read(folder="/Music/Bench/")
        self.assertEqual(set(out), {"clip one", "clip_two"})


def build_anlz(path, grid):
    """Build a minimal ANLZ .DAT following the public layout: PMAI header, PPTH, PQTZ."""
    raw_path = path.encode("utf-16-be") + b"\x00\x00"
    ppth = b"PPTH" + struct.pack(">III", 16, 16 + len(raw_path), len(raw_path)) + raw_path
    entries = b"".join(struct.pack(">HHI", b, int(round(bpm * 100)), int(round(t * 1000))) for b, bpm, t in grid)
    pqtz = b"PQTZ" + struct.pack(">IIIII", 24, 24 + len(entries), 0, 0x00800000, len(grid)) + entries
    body = ppth + pqtz
    return b"PMAI" + struct.pack(">II", 28, 28 + len(body)) + b"\x00" * 16 + body


class RekordboxAnlzTests(unittest.TestCase):
    def test_parse(self):
        grid = [(1, 128.0, 0.025), (2, 128.0, 0.494), (3, 128.0, 0.963), (4, 128.0, 1.431), (1, 128.0, 1.900)]
        path, g = rekordbox_anlz.parse_dat(build_anlz("/Music/Bench/song one.wav", grid))
        self.assertEqual(path, "/Music/Bench/song one.wav")
        self.assertEqual([(b, bpm) for b, bpm, _ in g], [(b, 128.0) for b, _, _ in grid])
        self.assertAlmostEqual(g[2][2], 0.963)

    def test_read_folder(self):
        grid = [(1, 126.0, 0.1), (2, 126.0, 0.576), (3, 126.0, 1.052), (4, 126.0, 1.529), (1, 126.0, 2.005)]
        with tempfile.TemporaryDirectory() as d:
            sub = os.path.join(d, "PIONEER", "USBANLZ", "abc", "def")
            os.makedirs(sub)
            write_file(os.path.join(sub, "ANLZ0000.DAT"), build_anlz("C:\\Music\\Bench\\clip_a.wav", grid))
            write_file(os.path.join(sub, "ANLZ0000.EXT"), b"ignored")
            write_file(os.path.join(sub, "junk.DAT"), b"ignored")
            sub2 = os.path.join(d, "PIONEER", "USBANLZ", "ghi", "jkl")
            os.makedirs(sub2)
            write_file(os.path.join(sub2, "ANLZ0000.DAT"), build_anlz("/Music/Bench/clip_b.wav", []))
            out = rekordbox_anlz.read(d)
        self.assertEqual(out["clip_a"]["downbeats"], [0.1, 2.005])
        self.assertEqual(out["clip_a"]["bpm"], 126.0)
        self.assertEqual(len(out["clip_a"]["beats"]), 5)
        self.assertIn("error", out["clip_b"])

    def test_not_anlz(self):
        with self.assertRaises(ValueError):
            rekordbox_anlz.parse_dat(b"XXXX" + b"\x00" * 40)


class SeratoTests(unittest.TestCase):
    def test_with_injected_reader(self):
        def fake_reader(path, timeline="serato"):
            name = os.path.basename(path)
            if name == "analysed.wav":
                return {"beats": [1.0, 1.5, 2.0, 2.5, 3.0], "beat_in_bar": [1, 2, 3, 4, 1], "bpm": 120.0}
            if name == "broken.wav":
                raise RuntimeError("bad tag")
            return None
        with tempfile.TemporaryDirectory() as d:
            for n in ("analysed.wav", "plain.wav", "broken.wav", "notes.txt"):
                write_file(os.path.join(d, n), b"")
            out = serato.read(d, reader=fake_reader, shift_ms=10)
        self.assertEqual(set(out), {"analysed", "plain", "broken"})
        self.assertEqual(out["analysed"]["beats"][0], 1.01)
        self.assertEqual(out["analysed"]["downbeats"], [1.01, 3.01])
        self.assertIn("no Serato BeatGrid", out["plain"]["error"])
        self.assertIn("bad tag", out["broken"]["error"])

    def test_without_serato_reader_installed(self):
        saved = sys.modules.pop("serato_reader", None)
        sys.modules["serato_reader"] = None                          # makes the import raise ImportError
        try:
            with self.assertRaises(SystemExit):
                serato.read(tempfile.gettempdir())
        finally:
            sys.modules.pop("serato_reader", None)
            if saved is not None:
                sys.modules["serato_reader"] = saved


if __name__ == "__main__":
    unittest.main()
