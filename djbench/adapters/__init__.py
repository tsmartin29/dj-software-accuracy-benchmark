"""Adapters: read what a DJ app itself wrote about each track and turn it into the contender format
{clip_id: {"beats": [...], "downbeats": [...], "bpm": 124.0, "key": "8A"}}.

An adapter only READS. It never writes to the app's library or to your audio files. Clip id = the audio file's name without its extension.
"""
import json
import os


def save_contender(path, data):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f, separators=(",", ":"))


def expand_grid(markers, end_s):
    """Turn tempo markers into beat times.

    markers: list of (time_s, bpm, beat_in_bar) sorted by time; each marker starts a constant-tempo run at that time and says which
    beat of the bar (1-4) falls there. A run lasts until the next marker; the last run lasts until end_s.
    Returns (beats, downbeats, bpm_per_beat).
    """
    beats, downs, bpms = [], [], []
    for i, (t0, bpm, bib) in enumerate(markers):
        if bpm <= 0:
            continue
        last = i + 1 == len(markers)
        t1 = end_s if last else markers[i + 1][0]
        period = 60.0 / bpm
        k = 0
        while True:
            t = t0 + k * period
            if (t > t1 + 1e-9) if last else (t >= t1 - 1e-9):
                break
            beats.append(t)
            bpms.append(bpm)
            if (bib - 1 + k) % 4 == 0:
                downs.append(t)
            k += 1
    return beats, downs, bpms
