"""
audio-clip: Trim a WAV file to a specified time range.

Primary use case: extracting clean acoustic event segments (dog barks, alarms)
from longer recordings for MFCC feature training, where the full recording
contains too much ambient background around the event.

Usage:
    audio-clip INPUT [--start S] [--end E | --duration D] [--output PATH] [--sr RATE]

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import sys

import soundfile as sf

from .audio_clip_engine import clip_audio, load_audio


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="audio-clip",
        description="Trim a WAV file to a specified time range.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument("input", help="Path to the source WAV file")
    parser.add_argument(
        "--start",
        "-s",
        type=float,
        default=0.0,
        metavar="S",
        help="Clip start in seconds",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--end",
        "-e",
        type=float,
        default=None,
        metavar="E",
        help="Clip end in seconds (default: end of file)",
    )
    group.add_argument(
        "--duration",
        "-d",
        type=float,
        default=None,
        metavar="D",
        help="Clip length in seconds; sets end = start + duration",
    )
    parser.add_argument(
        "--output",
        "-o",
        default=None,
        metavar="PATH",
        help="Output file path (default: <input_dir>/clips/<stem>_<start>s_<end>s.wav)",
    )
    parser.add_argument(
        "--sr",
        type=int,
        default=None,
        metavar="RATE",
        help="Resample output to this sample rate (default: preserve source rate)",
    )

    args = parser.parse_args()

    # Resolve --duration into an explicit --end
    if args.duration is not None:
        args.end = args.start + args.duration

    # When --end is still None, peek at the file duration to resolve it
    if args.end is None:
        try:
            samples, sr, _ = load_audio(args.input)
        except FileNotFoundError as exc:
            print(f"error: {exc}", file=sys.stderr)
            sys.exit(1)
        n = samples.shape[0] if samples.ndim > 1 else len(samples)
        args.end = n / sr

    try:
        out_path = clip_audio(args.input, args.start, args.end, args.output, args.sr)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)

    info = sf.info(out_path)
    channels = "mono" if info.channels == 1 else f"{info.channels}ch"
    duration = args.end - args.start
    print(f"✂️   Clipped {duration:.1f}s → {out_path}  ({info.samplerate} Hz, {channels})")


if __name__ == "__main__":
    main()
