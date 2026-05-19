"""
Convert WAV recordings to WhatsApp-compatible formats (OGG/Opus, MP3, AAC).
"""

import argparse
import glob
import shutil
import subprocess
import sys
from pathlib import Path

FORMATS = {
    "ogg": {
        "ext": ".ogg",
        "codec_args": ["-c:a", "libopus", "-b:a", "64k", "-vbr", "on"],
        "label": "OGG/Opus (WhatsApp voice, smallest)",
    },
    "mp3": {
        "ext": ".mp3",
        "codec_args": ["-c:a", "libmp3lame", "-q:a", "2"],
        "label": "MP3 (universal)",
    },
    "aac": {
        "ext": ".m4a",
        "codec_args": ["-c:a", "aac", "-b:a", "128k"],
        "label": "AAC/M4A (Apple-friendly)",
    },
}

DEFAULT_FORMATS = ["ogg"]


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        print("Error: ffmpeg is not installed or not on PATH.", file=sys.stderr)
        print("  Install it with:  sudo apt install ffmpeg", file=sys.stderr)
        sys.exit(1)


def collect_inputs(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            paths.extend(sorted(p.glob("*.wav")))
        elif p.is_file():
            paths.append(p)
        else:
            matched = sorted(Path(g) for g in glob.glob(inp))
            if not matched:
                print(f"  Warning: no files matched '{inp}'", file=sys.stderr)
            paths.extend(matched)

    seen: set[Path] = set()
    result: list[Path] = []
    for p in paths:
        if p.suffix.lower() != ".wav":
            print(f"  Skipping non-WAV file: {p.name}", file=sys.stderr)
            continue
        if p not in seen:
            seen.add(p)
            result.append(p)
    return result


def convert(src: Path, fmt: str, out_dir: Path | None, overwrite: bool) -> bool:
    spec = FORMATS[fmt]
    dest_dir = out_dir if out_dir else src.parent
    dest = dest_dir / (src.stem + spec["ext"])

    if dest.exists() and not overwrite:
        print(f"  [skip] {dest.name} already exists (--overwrite to replace)")
        return True

    dest_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "ffmpeg",
        "-y" if overwrite else "-n",
        "-i",
        str(src),
        *spec["codec_args"],
        str(dest),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  [fail] {src.name} → {dest.name}")
        print(result.stderr[-300:], file=sys.stderr)
        return False

    size_kb = dest.stat().st_size / 1024
    print(f"  [ok]   {src.name} → {dest.name}  ({size_kb:.0f} KB)")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Convert WAV recordings to WhatsApp-compatible formats.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="\n".join(f"  {k:<6} {v['label']}" for k, v in FORMATS.items()),
    )
    parser.add_argument(
        "inputs", nargs="+", metavar="FILE_OR_DIR", help="WAV file(s), director(ies), or glob pattern(s)"
    )
    parser.add_argument(
        "--format",
        "-f",
        nargs="+",
        choices=list(FORMATS),
        default=DEFAULT_FORMATS,
        metavar="FMT",
        dest="formats",
        help=f"output format(s): ogg mp3 aac  (default: {' '.join(DEFAULT_FORMATS)})",
    )
    parser.add_argument(
        "--out", "-o", metavar="DIR", help="output directory (default: same folder as each source file)"
    )
    parser.add_argument("--overwrite", action="store_true", help="overwrite existing output files")
    return parser


def main() -> None:
    check_ffmpeg()
    parser = build_parser()
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else None
    wav_files = collect_inputs(args.inputs)

    if not wav_files:
        print("No WAV files found.")
        sys.exit(0)

    total = len(wav_files) * len(args.formats)
    print(f"Converting {len(wav_files)} file(s) → {', '.join(args.formats).upper()}  ({total} output(s))\n")

    ok = fail = 0
    for wav in wav_files:
        for fmt in args.formats:
            if convert(wav, fmt, out_dir, args.overwrite):
                ok += 1
            else:
                fail += 1

    print(f"\nDone: {ok} succeeded, {fail} failed.")
    if fail:
        sys.exit(1)


if __name__ == "__main__":
    main()
