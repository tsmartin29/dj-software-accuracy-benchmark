"""Serato DJ beat grids, read from the "BeatGrid" / "Tempo Map" tags Serato writes inside your audio files.

Uses the serato-reader package (read-only; https://github.com/tsmartin29/serato-reader, pip install serato-reader), imported only
when you call read() so the rest of djbench works without it. Pass `reader=` to inject another implementation (the tests do).

Serato writes the tags only for tracks it has analysed and only into files it was allowed to write to; a file without the tag is
reported as an error entry (a miss). timeline="serato" keeps Serato's own positions; timeline="audio" moves AAC/M4A positions onto
the timeline other players use (the encoder-delay shift) - use it only if your truth timeline is the decoded audio.

Clip id = file name without extension.
"""
import os

AUDIO_EXT = {".wav", ".aiff", ".aif", ".mp3", ".flac", ".m4a", ".ogg"}


def read(folder, timeline="serato", shift_ms=0.0, reader=None):
    if reader is None:
        try:
            from serato_reader import read_beatgrid as reader
        except ImportError as e:
            raise SystemExit("the Serato adapter needs serato-reader: pip install serato-reader") from e
    out = {}
    for f in sorted(os.listdir(folder)):
        name, ext = os.path.splitext(f)
        if ext.lower() not in AUDIO_EXT:
            continue
        try:
            g = reader(os.path.join(folder, f), timeline=timeline)
        except Exception as e:                                      # one unreadable file must not stop the run
            out[name] = {"error": repr(e)[:200]}
            continue
        if not g or not g.get("beats"):
            out[name] = {"error": "no Serato BeatGrid tag (not analysed?)"}
            continue
        sh = shift_ms / 1000.0
        out[name] = {"beats": [round(b + sh, 4) for b in g["beats"]],
                     "downbeats": [round(b + sh, 4) for b, n in zip(g["beats"], g["beat_in_bar"]) if n == 1],
                     "bpm": g.get("bpm")}
    return out
