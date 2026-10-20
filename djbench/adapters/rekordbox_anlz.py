"""rekordbox analysis files (ANLZ0000.DAT), read-only.

rekordbox stores its analysis next to the database, in .../PIONEER/USBANLZ/<xxx>/<yyyyyyyy-...>/ANLZ0000.DAT (and on every exported
USB drive). Point this adapter at that folder (or a copy of it): it needs no database and no password. The file format is documented
by Deep Symmetry's reverse-engineering notes (https://djl-analysis.deepsymmetry.org/rekordbox-export-analysis/anlz.html).

Layout used here (all numbers big-endian):
  file header  "PMAI", u32 header length, u32 file length, ...
  then tagged sections: 4-byte tag, u32 header length, u32 section length, body
  PPTH  path of the audio file, UTF-16BE (the body starts with a u32 byte length)
  PQTZ  the beat grid: after the 12-byte section header, two u32 fields, a u32 entry count at offset 20, and from the end of the
        section header 8-byte entries: u16 beat number in the bar (1-4), u16 tempo in 1/100 BPM, u32 time in milliseconds
Times are milliseconds from rekordbox's 0:00 of the audio file.

Clip id = file name (without extension) of the path stored in PPTH.
"""
import os
import struct


def sections(data):
    if data[:4] != b"PMAI":
        raise ValueError("not an ANLZ file")
    (hl,) = struct.unpack_from(">I", data, 4)
    o = hl
    while o + 12 <= len(data):
        tag = data[o:o + 4]
        h, t = struct.unpack_from(">II", data, o + 4)
        if t < 12:
            raise ValueError(f"corrupt section {tag!r} at {o}")
        yield tag, o, h, t
        o += t


def parse_dat(data):
    """Return (audio_path or None, [(beat_in_bar, bpm, time_s), ...] or [])."""
    path, grid = None, []
    for tag, o, h, t in sections(data):
        if tag == b"PPTH":
            (n,) = struct.unpack_from(">I", data, o + 12)
            raw = data[o + 16:o + 16 + n]
            path = raw.decode("utf-16-be").rstrip("\x00")
        elif tag == b"PQTZ":
            (count,) = struct.unpack_from(">I", data, o + 20)
            for i in range(count):
                bib, tempo, ms = struct.unpack_from(">HHI", data, o + h + 8 * i)
                grid.append((bib, tempo / 100.0, ms / 1000.0))
    return path, grid


def read(folder):
    """Scan `folder` recursively for ANLZ*.DAT files and return the contender dict."""
    out = {}
    for dp, _, files in os.walk(folder):
        for f in sorted(files):
            if not (f.upper().startswith("ANLZ") and f.upper().endswith(".DAT")):
                continue
            with open(os.path.join(dp, f), "rb") as fh:
                data = fh.read()
            try:
                path, grid = parse_dat(data)
            except (ValueError, struct.error) as e:
                out[f"unreadable:{os.path.join(dp, f)}"] = {"error": str(e)}
                continue
            if not path:
                continue
            cid = os.path.splitext(os.path.basename(path.replace("\\", "/")))[0]
            if not grid:
                out[cid] = {"error": "no PQTZ beat grid in the ANLZ file"}
                continue
            out[cid] = {"beats": [round(t, 4) for _, _, t in grid],
                        "downbeats": [round(t, 4) for b, _, t in grid if b == 1],
                        "bpm": max(set(b for _, b, _ in grid), key=[b for _, b, _ in grid].count)}
    return out
