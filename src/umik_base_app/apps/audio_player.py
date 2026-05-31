"""
Headless audio file player.

Plays audio files in sequence. Key bindings during playback:
  Space / Enter  – skip to next file
  p              – pause / resume
  r              – replay current file from the start
  c              – open current file in the browser clip editor (audio-tools-clip)
  x              – quick-clip: prompt for start/end, run audio-clip, then resume
  d              – delete current file (asks for confirmation)
  q              – quit
"""

import argparse
import glob
import select
import subprocess
import sys
import termios
import time
import tty
from pathlib import Path

import sounddevice as sd
import soundfile as sf

AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".au"}


def _collect_files(inputs: list[str]) -> list[Path]:
    paths: list[Path] = []
    for inp in inputs:
        p = Path(inp)
        if p.is_dir():
            paths.extend(f for f in sorted(p.iterdir()) if f.suffix.lower() in AUDIO_EXTENSIONS)
        elif p.is_file():
            paths.append(p)
        else:
            matched = sorted(Path(g) for g in glob.glob(inp))
            if not matched:
                print(f"Warning: no files matched '{inp}'", file=sys.stderr)
            paths.extend(matched)

    seen: set[Path] = set()
    result: list[Path] = []
    for p in paths:
        if p.suffix.lower() not in AUDIO_EXTENSIONS:
            print(f"  [skip] {p.name}  (unsupported format)", file=sys.stderr)
            continue
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            result.append(p)
    return result


def _fmt(seconds: float) -> str:
    m = int(seconds // 60)
    s = int(seconds % 60)
    return f"{m}:{s:02d}"


def _is_playing() -> bool:
    try:
        return sd.get_stream().active
    except Exception:
        return False


def _read_char(timeout: float = 0.1) -> str | None:
    """Return one character if available within timeout, else None."""
    if select.select([sys.stdin], [], [], timeout)[0]:
        return sys.stdin.read(1)
    return None


def _play_file(path: Path, index: int, total: int, old_settings: list | None = None) -> str:
    """
    Play one file. Returns 'next', 'replay', 'delete', or 'quit'.
    """
    try:
        data, samplerate = sf.read(str(path), dtype="float32", always_2d=False)
    except Exception as e:
        print(f"\n  [skip] {path.name}: {e}")
        return "next"

    duration = len(data) / samplerate
    ch_label = "stereo" if data.ndim > 1 else "mono"

    print(f"\n{'─' * 58}")
    print(f"  [{index}/{total}]  {path.name}")
    print(f"  {_fmt(duration)}  ·  {int(samplerate)} Hz  ·  {ch_label}")
    print("  [Spc] next  [b] prev  [p] pause  [r] replay  [u] clip-UI  [c] clip  [d] delete  [q] quit\n")

    def _start_from(offset: float) -> None:
        start_sample = int(offset * samplerate)
        sd.play(data[start_sample:], samplerate)

    _start_from(0.0)
    start = time.monotonic()
    paused = False
    elapsed = 0.0

    while True:
        if not paused:
            elapsed = min(time.monotonic() - start, duration)

        filled = int((elapsed / duration) * 30) if duration > 0 else 0
        bar = "█" * filled + "░" * (30 - filled)

        if paused:
            print(f"\r  {bar}  {_fmt(elapsed)} / {_fmt(duration)}  [PAUSED]  ", end="", flush=True)
        else:
            print(f"\r  {bar}  {_fmt(elapsed)} / {_fmt(duration)}  ", end="", flush=True)

        if not paused and not _is_playing():
            print()
            return "next"

        ch = _read_char()
        if ch is None:
            continue

        if ch in ("\n", "\r", " "):
            sd.stop()
            print()
            return "next"

        elif ch in ("p", "P"):
            if paused:
                paused = False
                start = time.monotonic() - elapsed
                _start_from(elapsed)
            else:
                elapsed = min(time.monotonic() - start, duration)
                sd.stop()
                paused = True

        elif ch in ("b", "B"):
            sd.stop()
            print()
            return "prev"

        elif ch in ("r", "R"):
            sd.stop()
            print()
            return "replay"

        elif ch in ("u", "U"):
            # Open browser clip editor in background; player keeps running
            subprocess.Popen(
                ["audio-tools-clip", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            print("\n  🌐 Clip editor opened → http://localhost:8768")
            # Reprint the progress bar on the next line
            print()

        elif ch in ("c", "C"):
            # Quick-clip: prompt for start/end, run audio-clip, resume
            saved_elapsed = elapsed if paused else min(time.monotonic() - start, duration)
            sd.stop()
            if old_settings is not None:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            print(f"\n\n  Quick-clip  '{path.name}'  (0 – {duration:.2f}s)")
            try:
                start_s = input("  Start (s): ").strip()
                end_s = input("  End   (s): ").strip()
                cmd = ["audio-clip", str(path), "--start", start_s, "--end", end_s]
                subprocess.run(cmd)
            except (ValueError, KeyboardInterrupt):
                print("  Cancelled.")
            finally:
                if old_settings is not None:
                    tty.setcbreak(sys.stdin.fileno())
            print()
            # Resume from saved position
            _start_from(saved_elapsed)
            start = time.monotonic() - saved_elapsed
            elapsed = saved_elapsed
            paused = False

        elif ch in ("d", "D"):
            sd.stop()
            print(f"\n\n  Delete '{path.name}'? [y/N] ", end="", flush=True)
            confirm = _read_char(timeout=30.0)
            print(confirm or "n")
            if confirm in ("y", "Y"):
                print()
                return "delete"
            # Not confirmed — resume from where we left off
            print()
            _start_from(elapsed)
            start = time.monotonic() - elapsed
            paused = False

        elif ch in ("q", "Q"):
            sd.stop()
            print()
            return "quit"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="audio-tools-play",
        description="Play audio files from the terminal.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Supported formats: WAV, FLAC, OGG, AIFF\n\n"
            "Examples:\n"
            "  audio-tools --play recording.wav\n"
            "  audio-tools --play recordings/\n"
            "  audio-tools --play file1.wav file2.flac\n"
        ),
    )
    parser.add_argument(
        "inputs",
        nargs="+",
        metavar="FILE_OR_DIR",
        help="Audio file(s) or director(ies) to play",
    )
    args = parser.parse_args()

    files = _collect_files(args.inputs)
    if not files:
        print("No supported audio files found.")
        sys.exit(0)

    print(f"\naudio-tools player  ·  {len(files)} file(s) queued")

    if not sys.stdin.isatty():
        # Non-interactive: play all files straight through
        for i, f in enumerate(files, 1):
            try:
                data, samplerate = sf.read(str(f), dtype="float32", always_2d=False)
                print(f"  [{i}/{len(files)}]  {f.name}")
                sd.play(data, samplerate)
                sd.wait()
            except Exception as e:
                print(f"  [skip] {f.name}: {e}", file=sys.stderr)
        print("\nDone.")
        return

    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        i = 0
        while i < len(files):
            action = _play_file(files[i], i + 1, len(files), old_settings)
            if action == "next":
                i += 1
            elif action == "prev":
                i = max(0, i - 1)
            elif action == "replay":
                pass  # stay on same index
            elif action == "delete":
                try:
                    files[i].unlink()
                    print(f"  🗑  Deleted {files[i].name}")
                except OSError as e:
                    print(f"  Could not delete {files[i].name}: {e}", file=sys.stderr)
                i += 1
            elif action == "quit":
                break
    except KeyboardInterrupt:
        sd.stop()
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
        sd.stop()

    print("\nDone.")


if __name__ == "__main__":
    main()
