"""Command line: djbench fetch ..., djbench convert ..., djbench score ..."""
import argparse
import sys

from . import datasets, score as S
from .adapters import generic, rekordbox_anlz, rekordbox_xml, save_contender, serato


def main(argv=None):
    ap = argparse.ArgumentParser(prog="djbench", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="download and prepare a public dataset")
    f.add_argument("what", choices=["annotations", "gtzan", "giantsteps"])
    f.add_argument("--data", default="data")
    f.add_argument("--tarball", help="gtzan: use this genres.tar.gz instead of downloading")
    f.add_argument("--audio", action="store_true", help="giantsteps: also download the audio previews (about 1.5 GB for both sets)")

    c = sub.add_parser("convert", help="read a DJ app's own analysis output into the contender format")
    c.add_argument("adapter", choices=["rekordbox-xml", "rekordbox-anlz", "serato", "csv"])
    c.add_argument("source", help="rekordbox-xml: the exported .xml; rekordbox-anlz: a folder with ANLZ files; serato: a folder of audio files; csv: the .csv")
    c.add_argument("--out", required=True)
    c.add_argument("--folder", help="rekordbox-xml: keep only tracks whose Location contains this text")
    c.add_argument("--timeline", default="serato", choices=["serato", "audio"], help="serato adapter: see the adapter's doc")
    c.add_argument("--shift-ms", type=float, default=0.0, help="serato adapter: add a constant to every beat (sensitivity check)")

    s = sub.add_parser("score", help="score contenders against a truth file")
    s.add_argument("--truth", required=True)
    s.add_argument("contenders", nargs="+", help="contender JSON files; the first is the baseline for the difference tables")
    s.add_argument("--json", help="write the full result here")
    s.add_argument("--include", help="regex on clip ids, e.g. 'disco|pop|hiphop' for the DJ-relevant GTZAN genres")
    s.add_argument("--ids-file", help="text file of clip ids to keep")
    s.add_argument("--only-common", action="store_true", help="score only clips every contender produced")
    s.add_argument("--bootstrap", type=int, default=10000)
    s.add_argument("--seed", type=int, default=0)

    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        if a.what == "annotations":
            datasets.fetch_annotations(a.data)
        elif a.what == "gtzan":
            datasets.fetch_gtzan(a.data, a.tarball)
        else:
            datasets.fetch_giantsteps(a.data, a.audio)
    elif a.cmd == "convert":
        if a.adapter == "rekordbox-xml":
            data = rekordbox_xml.read(a.source, a.folder)
        elif a.adapter == "rekordbox-anlz":
            data = rekordbox_anlz.read(a.source)
        elif a.adapter == "serato":
            data = serato.read(a.source, timeline=a.timeline, shift_ms=a.shift_ms)
        else:
            data = generic.read_csv(a.source)
        save_contender(a.out, data)
        print(f"{len(data)} clips, {sum('beats' in v or 'bpm' in v or 'key' in v for v in data.values())} with output, "
              f"{sum('error' in v for v in data.values())} errors -> {a.out}")
    else:
        S.run(a.truth, a.contenders, out_json=a.json, include=a.include, ids_file=a.ids_file,
              only_common=a.only_common, n_boot=a.bootstrap, seed=a.seed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
