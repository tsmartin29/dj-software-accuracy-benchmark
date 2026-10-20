"""The truth file: independent, human-made answers for a set of clips.

    {"set": "gtzan", "source": "...", "clips": {"gtzan_blues_00000": {"beats": [0.217, ...], "downbeats": [1.173, ...], "bpm": 125.0, "key": "F# minor"}}}

Every clip may carry any of beats / downbeats / bpm / key; a metric is scored only where the truth has the field.
The clip id is the audio file's name without its extension: it is how a contender's output is matched to the truth, so the audio
that you import into the DJ software must be named <clip id>.<ext> (the dataset prep commands make such a folder).
"""
import json
import os
import re

import numpy as np


def load_truth(path):
    with open(path) as f:
        d = json.load(f)
    if "clips" not in d:
        raise ValueError(f"{path}: not a truth file (no 'clips')")
    return d


def save_truth(path, set_name, source, clips):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w") as f:
        json.dump({"set": set_name, "source": source, "clips": clips}, f, separators=(",", ":"))


def parse_beats_file(text):
    """Read a Beat This!-style .beats file: one beat per line, 'time' or 'time<TAB>beat_in_bar'.

    Returns (beats, downbeats_or_None). Downbeats are the lines whose beat number is 1; None when no line has a number
    (a set without downbeat labels, e.g. SMC). Blank lines are ignored."""
    times, nums = [], []
    for line in text.splitlines():
        parts = line.split()
        if not parts:
            continue
        times.append(float(parts[0]))
        nums.append(float(parts[1]) if len(parts) > 1 else None)
    beats = np.array(times, float)
    if not times or all(n is None for n in nums):
        return beats.tolist(), None
    down = [t for t, n in zip(times, nums) if n is not None and int(round(n)) == 1]
    return beats.tolist(), down


def convert_beat_annotations(set_dir, out_path, set_name=None):
    """<set_dir>/annotations/beats/*.beats  ->  truth file. Clip id = file name without '.beats'."""
    d = os.path.join(set_dir, "annotations", "beats")
    clips = {}
    for name in sorted(os.listdir(d)):
        if not name.endswith(".beats"):
            continue
        with open(os.path.join(d, name)) as f:
            beats, down = parse_beats_file(f.read())
        clip = {"beats": beats}
        if down is not None:
            clip["downbeats"] = down
        clips[name[:-len(".beats")]] = clip
    set_name = set_name or os.path.basename(os.path.normpath(set_dir))
    save_truth(out_path, set_name, "Beat This! annotations (Foscarin, Schlüter, Widmer; MIT)", clips)
    return len(clips)


def select_clips(clip_ids, include=None, ids_file=None):
    """Filter clip ids by a regex (--include) and/or a text file of ids (--ids-file, one per line)."""
    ids = list(clip_ids)
    if include:
        rx = re.compile(include)
        ids = [c for c in ids if rx.search(c)]
    if ids_file:
        with open(ids_file) as f:
            keep = {l.strip() for l in f if l.strip()}
        ids = [c for c in ids if c in keep]
    return ids
