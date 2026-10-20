"""Musical key parsing and scoring.

parse_key() understands the ways DJ software writes a key:
    "F# minor", "F#min", "Fm", "F#m", "Bb", "A major", "Abmaj"      (note names, sharps or flats)
    "8A", "11B"                                                       (Camelot wheel: A = minor, B = major)
    "1m", "12d"                                                       (Open Key: m = minor, d = major)
and returns (pitch_class 0-11, mode) with mode "major" or "minor", or None when it is not a key ("", "No key", "atonal").

Scoring follows the MIREX key task: exact 1.0, a perfect fifth away 0.5, relative major/minor 0.3, parallel major/minor 0.2,
anything else 0. On top of that, key_mix_compatible() is the DJ-flavoured question "would the two keys mix harmonically":
exact, fifth neighbour or relative (the same or an adjacent number on the Camelot wheel).
"""
import re

NOTE_TO_PC = {"c": 0, "d": 2, "e": 4, "f": 5, "g": 7, "a": 9, "b": 11}
PC_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Camelot number -> pitch class of the major (B) key; the minor (A) key on the same number is its relative minor (3 semitones down).
_CAMELOT_MAJOR = {1: 11, 2: 6, 3: 1, 4: 8, 5: 3, 6: 10, 7: 5, 8: 0, 9: 7, 10: 2, 11: 9, 12: 4}


def _camelot(num, letter):
    if num not in _CAMELOT_MAJOR:
        return None
    major_pc = _CAMELOT_MAJOR[num]
    if letter == "B":
        return major_pc, "major"
    return (major_pc - 3) % 12, "minor"


def parse_key(text):
    if text is None:
        return None
    s = str(text).strip()
    if not s or s.lower() in {"no key", "none", "n/a", "atonal", "?", "-"}:
        return None
    m = re.fullmatch(r"(\d{1,2})\s*([AaBb])", s)                      # Camelot
    if m:
        return _camelot(int(m.group(1)), m.group(2).upper())
    m = re.fullmatch(r"(\d{1,2})\s*([dDmM])", s)                      # Open Key
    if m:
        n = int(m.group(1))
        if not 1 <= n <= 12:
            return None
        return _camelot((n + 6) % 12 + 1, "B" if m.group(2).lower() == "d" else "A")
    m = re.fullmatch(r"([A-Ga-g])\s*([#♯b♭]?)\s*(.*)", s)             # note name
    if not m:
        return None
    pc = NOTE_TO_PC[m.group(1).lower()]
    acc = m.group(2)
    if acc in ("#", "♯"):
        pc += 1
    elif acc in ("b", "♭"):
        pc -= 1
    rest = m.group(3).strip().lower()
    if rest in ("", "maj", "major", "dur"):
        mode = "major"
    elif rest in ("m", "min", "minor", "moll"):
        mode = "minor"
    else:
        return None
    return pc % 12, mode


def to_label(key):
    """(pc, mode) -> 'F# minor' (the form mir_eval.key expects)."""
    return f"{PC_NAMES[key[0]]} {key[1]}"


def to_camelot(key):
    pc, mode = key
    major_pc = pc if mode == "major" else (pc + 3) % 12
    num = next(n for n, p in _CAMELOT_MAJOR.items() if p == major_pc)
    return f"{num}{'B' if mode == 'major' else 'A'}"


def key_relation(ref, est):
    """Name the relation of est to ref: exact, fifth, relative, parallel or other."""
    (rp, rm), (ep, em) = ref, est
    if (rp, rm) == (ep, em):
        return "exact"
    if rm == em and (ep - rp) % 12 in (5, 7):
        return "fifth"
    if rm != em:
        rel = (rp + 3) % 12 if rm == "minor" else (rp - 3) % 12     # relative of the reference
        if ep == rel:
            return "relative"
        if ep == rp:
            return "parallel"
    return "other"


MIREX_WEIGHTS = {"exact": 1.0, "fifth": 0.5, "relative": 0.3, "parallel": 0.2, "other": 0.0}


def key_score(ref, est):
    """MIREX weighted key score; 0.0 when est could not be parsed."""
    if ref is None:
        raise ValueError("reference key missing")
    if est is None:
        return 0.0
    return MIREX_WEIGHTS[key_relation(ref, est)]


def key_mix_compatible(ref, est):
    return 1.0 if est is not None and key_relation(ref, est) in ("exact", "fifth", "relative") else 0.0
