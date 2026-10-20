# Method

How `djbench` decides whether a DJ program's beat grid, tempo or key is *accurate*, and what it takes to say one program is better than another.

## 1. Agreement with another program is not accuracy

A common way to "test" a DJ program is to import the same tracks into it and into rekordbox (or Serato) and see how often the grids match. That measures **agreement**. It says nothing about who is right:

- If both programs make the same mistake (a grid half a beat late, a track at half tempo, the first beat of the bar in the wrong place) they agree perfectly and are both wrong.
- If the reference program is wrong and yours is right, you are punished for being right.
- The result changes when you swap the reference, so it cannot rank three programs.

Accuracy needs an answer key that does not come from any program under test. In this repository every program, including the one you care about, is a **contender** and is graded against the same independent truth. rekordbox and Serato are contenders, never the reference.

A related trap: the key or BPM tags already in your music files may have been written by one of the programs under test (rekordbox can write its analysis into the file tags). Never use tags from your own library as truth without knowing where they came from.

## 2. Independent truth

Acceptable answer keys, in order of strength:

1. **Human annotation** of public datasets: people listened and marked the beats, the bar starts, the tempo or the key. This repository fetches GTZAN beats and downbeats (via the Beat This! annotation bundle, which also contains Ballroom, SMC, Hainsworth, Harmonix and others), the GiantSteps tempo set and the GiantSteps key set.
2. **Synthetic audio with known truth**, such as a click track or a generated drum loop at a known tempo and offset. Perfect truth, but easy audio: it checks plumbing (time origin, bar numbering), not difficulty.
3. Signal-derived judges (for example, do the grid lines land on the track's own kick drum) are useful for music the datasets lack, but they are a model of truth, not truth. They are not part of this repository.

All annotation sets have faults. GTZAN in particular has known problems (repeated, mislabelled and distorted clips; see Sturm's analyses in the references) and was not made from DJ music. We use it because its beat annotations are public and widely used, and because its disco, pop and hip-hop genres are a rough proxy for dance music: `--include 'disco|pop|hiphop'`. Treat results on any single set as one piece of evidence and look for agreement across sets.

**Training contamination.** Many beat and key models were trained on these same public sets. If a contender (or a program that embeds such a model) saw the test clips in training, its score on them is optimistic. Find out and say so next to the number.

## 3. What is scored

All beat metrics come from [mir_eval](https://github.com/mir-evaluation/mir_eval). Per clip:

| Metric | Meaning |
|---|---|
| `F@20ms`, `F@35ms`, `F@70ms` | F-measure of beats: an estimated beat counts as correct if it is within the window of a reference beat (each used once). 70 ms is the usual literature value. DJs hear a grid that is 40 ms off, so the tighter windows are reported too. |
| `CMLt`, `AMLt` | Continuity: how much of the track is tracked on the correct metric level (CMLt) or on any acceptable level - double, half, off-beat (AMLt). A grid at half tempo scores low on CMLt and high on AMLt. |
| `DownF` | F-measure of downbeats (beat 1 of each bar) at 70 ms, only where both truth and contender have downbeats. Not trimmed. |
| `Acc1`, `Acc2` | Tempo within 4 % of the reference (Acc1), or also accepting 2x, 1/2, 3x, 1/3 (Acc2, Gouyon et al.). |
| `KeyScore`, `KeyExact`, `KeyMix` | MIREX weighted key score (exact 1.0, perfect fifth 0.5, relative major/minor 0.3, parallel 0.2); exact match; and "would mix harmonically" (exact, a fifth away, or relative: the same or neighbouring number on the Camelot wheel). |

Conventions you should know about:

- mir_eval ignores beats in the first 5 seconds of both sequences before comparing beats (the literature's convention). Downbeats are not trimmed.
- Beat time sets are sorted, de-duplicated and cleaned of negative or non-finite values before scoring.
- If the truth has no tempo, the reference tempo is the median inter-beat interval of the reference beats, which assumes a steady track.
- **A missing output is a miss**, not a skipped clip. A program that fails to analyse a track scores 0 on that track; coverage (how many clips it produced output for) is printed next to its scores. If you want to compare only on clips every program handled, use `--only-common`, and say that you did.
- A metric a program never reports (a program that writes no downbeats) is not scored for it at all; it is not given a zero.

## 4. Running the contenders fairly

- Feed every program the **same audio files**, named `<clip id>.<ext>`. Use WAV: for MP3 and AAC, programs disagree about where time zero is (the encoder delay), which shifts every beat by tens of milliseconds and turns a timeline convention into an "accuracy" difference. If you must use a lossy format, check a click-track fixture first to see each program's offset.
- Use each program's **default analysis**, and write down the version, the analysis settings (for example, whether tempo changes were enabled) and the operating system. A program that offers a "dynamic" analysis mode and was run in the default constant mode is scored as it was run.
- Do not fix offsets by fitting them to the truth. If a program has a systematic offset, that is part of its accuracy; if you believe it is a timeline convention, show the evidence (a click-track test) and report both numbers.
- Read the programs' **own stored analysis** (the adapters). Do not re-derive grids from their tempo and first-beat fields unless that is all the program exports, and note the loss of precision if you do: rekordbox's XML export stores BPM with two decimals, so extrapolating a constant grid across a long track can drift by milliseconds (0.005 BPM at 128 BPM is about 5 ms per two minutes). The ANLZ adapter reads per-beat times exactly as rekordbox stored them.

## 5. Confidence intervals and significance

A mean over clips is an estimate. To say one program is better than another you need to know whether the difference is larger than the noise from which clips happened to be in the set.

- **Unit of resampling: the clip.** Beats inside a track are not independent; resampling beats would give intervals far too narrow.
- **Per-program 95 % interval:** percentile bootstrap of the mean over clips (default 10,000 resamples, fixed seed so results are reproducible).
- **Differences between two programs:** computed per clip on the same clips (paired), with a paired-bootstrap 95 % interval of the mean difference and a Wilcoxon signed-rank test on the per-clip differences. Pairing removes the clip-difficulty noise that both programs share.
- **Many metrics at once:** the p-values of one comparison are also given Holm-Bonferroni adjusted, because reading eleven metrics and picking the one that looks good inflates false positives.
- **Practical vs statistical significance:** with hundreds of clips a 0.5 point difference can be "significant" and irrelevant. Look at the interval, not only the p-value.
- **One set is not enough.** Only claim "better" when the interval of the difference excludes zero on at least two independent sets (for example GTZAN and Ballroom for beats, GiantSteps for tempo and key). Tied or opposite results on another set are findings too, so publish them.
- Reporting rule: always show the number of clips and the coverage next to every table.

## 6. Limits

- Public sets are small and genre-limited; they are not your listeners' music.
- Human annotations are themselves imperfect (annotators disagree on where a beat is by a few milliseconds, more on swung music). Windows tighter than 20 ms mostly measure annotation noise.
- The key datasets were built from community corrections of Beatport's key labels; they are a good yardstick, not an oracle.
- Programs change between versions. Pin and publish the version for every number.

## 7. Status of results

No numbers are published from this repository yet. The full run of rekordbox, Serato and other programs on the public sets is still being done. The commands in the README reproduce a run end to end on your own machine.

## References

- C. Raffel, B. McFee, E. J. Humphrey, J. Salamon, O. Nieto, D. Liang, D. P. W. Ellis: "mir_eval: A Transparent Implementation of Common MIR Metrics", ISMIR 2014. <https://github.com/mir-evaluation/mir_eval> (MIT)
- F. Foscarin, J. Schlüter, G. Widmer: "Beat This! Accurate Beat Tracking Without DBN Postprocessing", ISMIR 2024. Annotation bundle: <https://github.com/CPJKU/beat_this_annotations> and Zenodo record 13922116 (MIT); the repository lists the original annotators of every set, please cite them when you use a set.
- G. Tzanetakis, P. Cook: "Musical genre classification of audio signals", IEEE Transactions on Speech and Audio Processing, 2002 (GTZAN).
- B. L. Sturm: "The GTZAN dataset: Its contents, its faults, their effects on evaluation, and its future use", Journal of New Music Research, 2014.
- P. Knees, A. Faraldo, P. Herrera, R. Vogl, S. Böck, F. Hörschläger, M. Le Goff: "Two data sets for tempo estimation and key detection in electronic dance music annotated from user corrections", ISMIR 2015 (GiantSteps tempo and key). <https://github.com/GiantSteps>
- H. Schreiber, M. Müller: "A Crowdsourced Experiment for Tempo Estimation of Electronic Dance Music", ISMIR 2018 (GiantSteps tempo v2).
- F. Gouyon, A. Klapuri, S. Dixon, M. Alonso, G. Tzanetakis, C. Uhle, P. Cano: "An experimental comparison of audio tempo induction algorithms", IEEE Transactions on Audio, Speech and Language Processing, 2006 (Acc1, Acc2).
- M. E. P. Davies, N. Degara, M. D. Plumbley: "Evaluation methods for musical audio beat tracking algorithms", Queen Mary University of London technical report C4DM-TR-09-06, 2009 (continuity metrics).
- Deep Symmetry, "Rekordbox Analysis File Formats": <https://djl-analysis.deepsymmetry.org/rekordbox-export-analysis/anlz.html> (ANLZ layout used by the rekordbox adapter).
