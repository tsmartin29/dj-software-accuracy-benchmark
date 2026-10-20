# dj-software-accuracy-benchmark

Scores DJ software's beat grids, tempo and key against independent, human-labelled truth, not against another program.

Made by Tommy Martin. Built while running [ClubPlugins](https://clubplugins.com).

## Why

"How closely does it match rekordbox?" is a question about agreement, not accuracy: two programs can agree perfectly and both be wrong, and a program that is right gets punished for disagreeing with a wrong reference. This repository grades **every** program, rekordbox and Serato included, as a contender against the same human annotations (public datasets) and puts a bootstrap confidence interval and a significance test on every number. [METHOD.md](METHOD.md) explains why in more detail and what the numbers mean.

**Results: coming.** The full run of rekordbox, Serato and other programs on the public sets is not finished, so this repository publishes no numbers yet. Everything you need to reproduce a run on your own machine is here.

## What is in the box

| Path | What |
|---|---|
| `djbench/metrics.py` | per-clip metrics: beat F-measure at 20 / 35 / 70 ms, continuity (CMLt, AMLt), downbeat F, tempo Acc1 / Acc2, key (MIREX score, exact, mixes-harmonically). Beat metrics are [mir_eval](https://github.com/mir-evaluation/mir_eval)'s |
| `djbench/stats.py` | bootstrap 95 % intervals over clips, paired comparison (bootstrap + Wilcoxon), Holm correction |
| `djbench/score.py`, `cli.py` | the scorer and the `djbench` command |
| `djbench/keys.py` | key parsing (note names, Camelot, Open Key) and scoring |
| `djbench/adapters/` | readers for what each app stored: rekordbox XML export, rekordbox ANLZ analysis files, Serato (BeatGrid / Tempo Map tags, through [serato-reader](https://github.com/tsmartin29/serato-reader)), and a generic JSON / CSV format for anything else |
| `djbench/datasets.py` | download and prepare public datasets from their official homes: Beat This! annotation bundle (GTZAN, Ballroom, SMC, ...), GTZAN audio, GiantSteps tempo and key |
| `METHOD.md` | the method: independent truth, metrics, fair running, significance, limits, references |
| `tests/` | 64 unit tests with synthetic beats of known answer, tiny synthetic fixtures for every adapter, the bootstrap and the dataset preparation |

Not included, on purpose: any dataset audio or annotations (everything is downloaded from the owners), any program's own analysis code, and any results.

## Install

Python 3.9 or newer.

```bash
git clone <this repo> dj-software-accuracy-benchmark && cd dj-software-accuracy-benchmark
python3 -m venv .venv && . .venv/bin/activate && pip install -U pip      # pip 21.3 or newer is needed for the editable install
pip install -e .                       # numpy, scipy, mir_eval
pip install serato-reader              # only for the Serato adapter (see its README if it is not on PyPI yet)
python -m unittest discover -s tests -t .        # optional: 64 tests, a few seconds
```

## Reproduce a run (GTZAN example)

1. **Get the truth and the audio** (about 1.2 GB for GTZAN audio, downloaded from the Marsyas project's host; GTZAN has no permanent home, so if the download fails fetch `genres.tar.gz` yourself and pass `--tarball`):

   ```bash
   djbench fetch annotations --data data                  # truth for GTZAN, Ballroom, SMC, ... -> data/truth/*.json
   djbench fetch gtzan --data data                        # audio -> data/audio/gtzan/gtzan_<genre>_<nnnnn>.wav
   ```

   The file names are the clip ids: keep them, they are how a program's output is matched to the truth.

2. **Import the folder `data/audio/gtzan` into each program and let it analyse the tracks** with its default settings. Write down the program version.

3. **Read each program's own result** into the contender format:

   ```bash
   # rekordbox: File > Export Collection in xml format ...
   djbench convert rekordbox-xml export.xml --out beats/rekordbox.json --folder gtzan
   # ... or read its analysis files (exact per-beat times); rekordbox keeps them under .../PIONEER/USBANLZ/
   djbench convert rekordbox-anlz /path/to/copy/of/USBANLZ --out beats/rekordbox.json
   # Serato writes the grid into the audio files' tags
   djbench convert serato data/audio/gtzan --out beats/serato.json
   # anything else: a CSV with columns clip,time,beat_in_bar,bpm,key
   djbench convert csv other_app.csv --out beats/other.json
   ```

   The adapters only read. Point them at a copy of an app's folders if you prefer.

4. **Score:**

   ```bash
   djbench score --truth data/truth/gtzan.json beats/rekordbox.json beats/serato.json beats/other.json \
       --include 'disco|pop|hiphop' --json scores/gtzan_dj.json
   ```

   The first file is the baseline for the difference tables. Output: per program, each metric's mean with a 95 % bootstrap interval and the number of clips; then for every other program the difference to the baseline with a paired 95 % interval, a Wilcoxon p-value and a Holm-adjusted p-value. A track a program did not analyse scores 0 (coverage is printed); `--only-common` restricts to tracks every program handled.

### Tempo and key (GiantSteps)

```bash
djbench fetch giantsteps --data data --audio     # annotations by git clone; audio from the dataset's own download locations, md5-checked
djbench score --truth data/truth/giantsteps_tempo_v2.json beats/rekordbox_gs.json beats/serato_gs.json
djbench score --truth data/truth/giantsteps_key.json     beats/rekordbox_gs.json beats/serato_gs.json
```

Audio files are named `gs_<id>.mp3`; for programs that read WAV more reliably, convert them (keep the names). Keys may be written as `F# minor`, `Am`, Camelot `8A` or Open Key `1m`; the scorer understands all of them.

## File formats

Truth file (`data/truth/<set>.json`):

```json
{"set": "gtzan", "source": "...", "clips": {"gtzan_blues_00000": {"beats": [0.217, 0.695], "downbeats": [1.173], "bpm": 125.0, "key": "F# minor"}}}
```

Contender file (the file name is the program's name in the tables):

```json
{"gtzan_blues_00000": {"beats": [0.21, 0.69], "downbeats": [1.17], "bpm": 125.1, "key": "8A"},
 "gtzan_blues_00001": {"error": "not analysed"}}
```

Any field may be missing. A field a program never reports is not scored (it is not a zero).

## Datasets and licences

Nothing from the datasets is stored in this repository. `djbench fetch` downloads from the owners' own locations and you are responsible for following their terms.

- **Beat This! annotations** (beats and downbeats for GTZAN, Ballroom, SMC, Hainsworth, Harmonix and more): Foscarin, Schlüter, Widmer, ISMIR 2024, [CPJKU/beat_this_annotations](https://github.com/CPJKU/beat_this_annotations), MIT. The repository's acknowledgements list the original annotators of each set; please cite them.
- **GTZAN** audio: Tzanetakis and Cook (2002). Its provenance and legal status are unclear and it has known faults (see METHOD.md). Use at your own judgement.
- **GiantSteps tempo and key**: Knees et al. (ISMIR 2015), Schreiber and Müller (ISMIR 2018) for tempo v2. The annotations come from [github.com/GiantSteps](https://github.com/GiantSteps); the audio are Beatport previews that the dataset's own scripts download. Check the dataset READMEs for terms before using the audio for anything beyond evaluation.
- **mir_eval**: Raffel et al., ISMIR 2014, MIT.
- The rekordbox ANLZ layout follows [Deep Symmetry's analysis notes](https://djl-analysis.deepsymmetry.org/rekordbox-export-analysis/anlz.html). rekordbox is a trademark of AlphaTheta Corporation, Serato of Serato Audio Research Limited; this project is not affiliated with either and only reads the files their programs write on your own computer.

## Known limits

- The Serato adapter depends on `serato-reader`; it needs files Serato has analysed and could write its tags to.
- rekordbox XML stores BPM with two decimals, so grids rebuilt from it can drift by milliseconds on long tracks; prefer the ANLZ adapter for exact times (METHOD.md, section 4).
- Programs that analyse MP3 or AAC may count time from a different origin than a decoder does. Use WAV (the GTZAN preparation does).
- There are no readers for formats we have not seen real files of (Traktor, Engine DJ, rbxport and others); use the CSV format, or send a reader with a tiny synthetic fixture.

## Licence

MIT. See `LICENSE`.

Made by Tommy Martin. Built while running [ClubPlugins](https://clubplugins.com).
