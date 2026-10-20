"""Fetch and prepare PUBLIC human-labelled datasets from their official homes.

Nothing here is redistributed by this repo: every command downloads from the dataset owners and checks what it can.
You are responsible for following each dataset's own terms (see README.md, "Datasets and licences").

    djbench fetch annotations --data data               Beat This! annotation bundle (GTZAN, Ballroom, SMC, ... beats and downbeats)
                                                          -> data/truth/<set>.json
    djbench fetch gtzan       --data data               GTZAN audio -> data/audio/gtzan/<clip id>.wav, ids match the annotations
    djbench fetch giantsteps  --data data [--audio]     GiantSteps tempo (v1, v2) and key annotations -> data/truth/giantsteps_*.json,
                                                          optionally the 2-minute audio previews -> data/audio/giantsteps/<id>.mp3
"""
import array
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import tarfile
import urllib.request
import wave
import zipfile

from . import truth as T

ANNOTATIONS_URLS = [
    "https://zenodo.org/records/13922116/files/beat_this_annotations.zip?download=1",     # Zenodo record of the ISMIR 2024 paper
    "https://github.com/CPJKU/beat_this_annotations/archive/refs/heads/main.zip",
]
# GTZAN has no stable home. The Marsyas project (the dataset's creators) hosts the tarball on Hugging Face; the original
# university server is tried second. If both fail, download it yourself and pass --tarball.
GTZAN_URLS = [
    "https://huggingface.co/datasets/marsyas/gtzan/resolve/main/data/genres.tar.gz",
    "http://opihi.cs.uvic.ca/sound/genres.tar.gz",
]
GIANTSTEPS_REPOS = {
    "tempo": "https://github.com/GiantSteps/giantsteps-tempo-dataset.git",
    "key": "https://github.com/GiantSteps/giantsteps-key-dataset.git",
}
GIANTSTEPS_AUDIO = ["https://www.cp.jku.at/datasets/giantsteps/backup/{name}", "https://geo-samples.beatport.com/lofi/{name}"]


# ------------------------------------------------------------------ helpers
def download(urls, dest, expect_size=None):
    """Try each URL in turn; stream to dest + '.part' and rename. Returns the URL that worked."""
    os.makedirs(os.path.dirname(os.path.abspath(dest)), exist_ok=True)
    last = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "djbench/0.1"})
            with urllib.request.urlopen(req, timeout=60) as r, open(dest + ".part", "wb") as f:
                total = int(r.headers.get("Content-Length") or 0)
                got = 0
                while True:
                    b = r.read(1 << 20)
                    if not b:
                        break
                    f.write(b)
                    got += len(b)
                    if total:
                        print(f"\r  {got / 1e6:8.1f} / {total / 1e6:.1f} MB", end="", file=sys.stderr)
                print(file=sys.stderr)
            if total and got != total:
                raise IOError(f"short download: {got} of {total} bytes")
            if expect_size and got != expect_size:
                raise IOError(f"unexpected size {got}, expected {expect_size}")
            os.replace(dest + ".part", dest)
            return url
        except Exception as e:                                       # try the next source
            last = e
            print(f"  {url}: {e}", file=sys.stderr)
            if os.path.exists(dest + ".part"):
                os.remove(dest + ".part")
    raise SystemExit(f"could not download {os.path.basename(dest)} from any source (last error: {last}). Download it by hand, see README.")


def md5_of(path):
    h = hashlib.md5()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def safe_member(name):
    """Reject archive members that are absolute or climb out of the target folder."""
    p = os.path.normpath(name)
    return not (os.path.isabs(p) or p.startswith(".."))


# ------------------------------------------------------------------ Beat This! annotations
def fetch_annotations(data):
    zpath = os.path.join(data, "downloads", "beat_this_annotations.zip")
    if not os.path.exists(zpath):
        download(ANNOTATIONS_URLS, zpath)
    dest = os.path.join(data, "annotations")
    with zipfile.ZipFile(zpath) as z:
        for m in z.infolist():
            if not safe_member(m.filename):
                raise SystemExit(f"refusing unsafe path in zip: {m.filename}")
        z.extractall(dest)
    n = 0
    for root, dirs, _ in os.walk(dest):
        if "annotations" in dirs and os.path.isdir(os.path.join(root, "annotations", "beats")):
            set_dir = root
            name = os.path.basename(set_dir)
            c = T.convert_beat_annotations(set_dir, os.path.join(data, "truth", f"{name}.json"), name)
            print(f"truth/{name}.json: {c} clips")
            n += 1
    if n == 0:
        raise SystemExit("no <set>/annotations/beats folders found in the bundle")


# ------------------------------------------------------------------ GTZAN audio
def read_au(data):
    """Minimal reader for Sun/NeXT .au (what GTZAN ships): returns (rate, channels, little-endian 16-bit PCM bytes)."""
    if data[:4] != b".snd":
        raise ValueError("not a .au file")
    off, size, enc, rate, ch = struct.unpack(">5I", data[4:24])
    if enc != 3:
        raise ValueError(f"unsupported .au encoding {enc} (expected 16-bit linear PCM)")
    pcm = data[off:off + size] if size != 0xFFFFFFFF else data[off:]
    a = array.array("h")
    a.frombytes(pcm[:len(pcm) // 2 * 2])
    a.byteswap()                                                    # .au is big-endian, WAV little-endian: swap each 16-bit unit
    return rate, ch, a.tobytes()


def gtzan_clip_id(member_name):
    """'genres/blues/blues.00012.au' -> 'gtzan_blues_00012' (the ids used by the Beat This! annotations). None for other files."""
    parts = member_name.replace("\\", "/").split("/")
    base = parts[-1]
    if not base.endswith(".au") or len(parts) < 2:
        return None
    stem = base[:-3]
    genre, _, num = stem.partition(".")
    if not genre or not num.isdigit():
        return None
    return f"gtzan_{genre}_{num.zfill(5)}"


def prepare_gtzan(tarball, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    done = failed = 0
    with tarfile.open(tarball, "r:*") as tf:
        for m in tf:
            cid = gtzan_clip_id(m.name) if m.isfile() and safe_member(m.name) else None
            if not cid:
                continue
            dst = os.path.join(out_dir, cid + ".wav")
            if os.path.exists(dst):
                done += 1
                continue
            try:
                rate, ch, pcm = read_au(tf.extractfile(m).read())
                with wave.open(dst, "wb") as w:
                    w.setnchannels(ch)
                    w.setsampwidth(2)
                    w.setframerate(rate)
                    w.writeframes(pcm)
                done += 1
            except Exception as e:
                failed += 1
                print(f"  skipped {m.name}: {e}", file=sys.stderr)
    print(f"GTZAN: {done} clips in {out_dir}" + (f", {failed} unreadable (known: jazz.00054)" if failed else ""))


def fetch_gtzan(data, tarball=None):
    if tarball is None:
        tarball = os.path.join(data, "downloads", "genres.tar.gz")
        if not os.path.exists(tarball):
            print("downloading GTZAN (about 1.2 GB) ...")
            download(GTZAN_URLS, tarball)
    prepare_gtzan(tarball, os.path.join(data, "audio", "gtzan"))


# ------------------------------------------------------------------ GiantSteps
def read_first_line(path):
    with open(path) as f:
        return f.readline().strip()


def giantsteps_ids(folder, suffix):
    return sorted(n[:-len(suffix)] for n in os.listdir(folder) if n.endswith(suffix))


def build_giantsteps_truth(repo_dir, kind, out_dir, version="v2"):
    """kind 'tempo' (annotations_v2/tempo or annotations/tempo, *.LOFI.bpm) or 'key' (annotations/key, *.LOFI.key)."""
    clips = {}
    if kind == "tempo":
        d = os.path.join(repo_dir, "annotations_v2" if version == "v2" else "annotations", "tempo")
        for stem in giantsteps_ids(d, ".LOFI.bpm"):
            bpm = float(read_first_line(os.path.join(d, stem + ".LOFI.bpm")))
            if bpm > 0:                                              # v2 marks the 3 unlabeled tracks 0.0
                clips[f"gs_{stem}"] = {"bpm": bpm}
        name, src = f"giantsteps_tempo_{version}", "GiantSteps tempo dataset (Knees et al. 2015; Schreiber & Müller 2018 for v2)"
    else:
        d = os.path.join(repo_dir, "annotations", "key")
        for stem in giantsteps_ids(d, ".LOFI.key"):
            clips[f"gs_{stem}"] = {"key": read_first_line(os.path.join(d, stem + ".LOFI.key"))}
        name, src = "giantsteps_key", "GiantSteps key dataset (Knees et al. 2015)"
    T.save_truth(os.path.join(out_dir, f"{name}.json"), name, src, clips)
    print(f"truth/{name}.json: {len(clips)} clips")
    return clips


def clone(url, dest):
    if os.path.isdir(os.path.join(dest, ".git")):
        return
    if not shutil.which("git"):
        raise SystemExit("git is needed to fetch the GiantSteps annotations")
    subprocess.run(["git", "clone", "--depth", "1", url, dest], check=True)


def fetch_giantsteps_audio(repo_dir, out_dir, ids):
    """Download <id>.LOFI.mp3 for each id from the dataset's official locations and verify against the repo's md5 files."""
    os.makedirs(out_dir, exist_ok=True)
    ok = bad = 0
    for stem in ids:
        name = f"{stem}.LOFI.mp3"
        dst = os.path.join(out_dir, f"gs_{stem}.mp3")
        if os.path.exists(dst):
            ok += 1
            continue
        want = read_first_line(os.path.join(repo_dir, "md5", f"{stem}.LOFI.md5"))
        got = None
        for pat in GIANTSTEPS_AUDIO:
            try:
                download([pat.format(name=name)], dst)
                got = md5_of(dst)
                if got == want:
                    break
                os.remove(dst)
            except SystemExit:
                continue
        if got == want:
            ok += 1
        else:
            bad += 1
            print(f"  {name}: could not get a copy with the right md5", file=sys.stderr)
    print(f"GiantSteps audio: {ok} ok, {bad} failed, in {out_dir}")


def fetch_giantsteps(data, audio=False):
    work = os.path.join(data, "downloads")
    for kind, url in GIANTSTEPS_REPOS.items():
        repo = os.path.join(work, f"giantsteps-{kind}-dataset")
        clone(url, repo)
        if kind == "tempo":
            build_giantsteps_truth(repo, "tempo", os.path.join(data, "truth"), "v1")
            clips = build_giantsteps_truth(repo, "tempo", os.path.join(data, "truth"), "v2")
        else:
            clips = build_giantsteps_truth(repo, "key", os.path.join(data, "truth"))
        if audio:
            fetch_giantsteps_audio(repo, os.path.join(data, "audio", "giantsteps"), sorted(c[3:] for c in clips))
