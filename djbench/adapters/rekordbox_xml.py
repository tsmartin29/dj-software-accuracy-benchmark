"""rekordbox's "Export Collection in xml format" (File > Export Collection in xml format).

Each <TRACK> has Location (a file:// URL), BPM, Tonality (the key, as rekordbox is set to display it: note name or Camelot),
TotalTime (seconds) and one <TEMPO Inizio="0.025" Bpm="128.00" Metro="4/4" Battito="1"/> per constant-tempo run of the beat grid
(a track with a steady grid has one). Inizio is the time of the marker in seconds, Battito the beat of the bar (1-4) at the marker.
Beats are rebuilt by running each marker's tempo until the next marker (or TotalTime).

Limit: Bpm is written with two decimals. Rounding of up to 0.005 BPM moves a beat late in a track by about 5 ms per two minutes of
audio (arithmetic: 0.005/128 x 120 s). For per-beat positions exactly as rekordbox stores them, use the ANLZ adapter instead.
"""
import os
import urllib.parse
import xml.etree.ElementTree as ET

from . import expand_grid


def clip_id_from_location(loc):
    path = urllib.parse.unquote(urllib.parse.urlparse(loc).path) if loc.startswith("file:") else loc
    return os.path.splitext(os.path.basename(path.replace("\\", "/")))[0]


def read(xml_path, folder=None):
    """Return the contender dict for every track in the XML (optionally only tracks whose Location contains `folder`)."""
    root = ET.parse(xml_path).getroot()
    out = {}
    for tr in root.iter("TRACK"):
        loc = tr.get("Location")
        if not loc:
            continue
        if folder and folder not in urllib.parse.unquote(loc):
            continue
        cid = clip_id_from_location(loc)
        tempos = tr.findall("TEMPO")
        if not tempos:
            out[cid] = {"error": "no beat grid (TEMPO) in the XML - not analysed?"}
            continue
        total = float(tr.get("TotalTime") or 0)
        markers = sorted((float(t.get("Inizio")), float(t.get("Bpm")), int(t.get("Battito") or 1)) for t in tempos)
        end = total if total > 0 else markers[-1][0] + 600.0
        beats, downs, _ = expand_grid(markers, end)
        entry = {"beats": [round(b, 4) for b in beats], "downbeats": [round(d, 4) for d in downs]}
        bpm = tr.get("AverageBpm") or tr.get("BPM") or tempos[0].get("Bpm")
        if bpm:
            entry["bpm"] = float(bpm)
        ton = tr.get("Tonality")
        if ton:
            entry["key"] = ton
        out[cid] = entry
    return out
