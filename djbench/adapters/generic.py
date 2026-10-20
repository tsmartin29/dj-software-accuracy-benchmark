"""Generic formats, for any app you can get numbers out of.

JSON: the contender format itself ({clip_id: {"beats": [...], ...}}), nothing to convert.

CSV (one row per beat), header required:
    clip,time,beat_in_bar,bpm,key
    song_a,0.512,1,124.0,8A
    song_a,0.996,2,,
  - clip          clip id (audio file name without extension)
  - time          beat time in seconds
  - beat_in_bar   optional; rows with 1 become downbeats
  - bpm, key      optional, may sit on any row of the clip (the first non-empty value wins)
A clip with no 'time' at all but a bpm/key still counts (tempo/key only apps).
"""
import csv


def read_csv(path):
    out = {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            clip = (row.get("clip") or "").strip()
            if not clip:
                continue
            c = out.setdefault(clip, {"beats": [], "downbeats": []})
            t = (row.get("time") or "").strip()
            if t:
                c["beats"].append(float(t))
                bib = (row.get("beat_in_bar") or "").strip()
                if bib and int(float(bib)) == 1:
                    c["downbeats"].append(float(t))
            if "bpm" not in c and (row.get("bpm") or "").strip():
                c["bpm"] = float(row["bpm"])
            if "key" not in c and (row.get("key") or "").strip():
                c["key"] = row["key"].strip()
    for c in out.values():
        c["beats"].sort()
        c["downbeats"].sort()
        if not c["downbeats"]:
            del c["downbeats"]
    return out
