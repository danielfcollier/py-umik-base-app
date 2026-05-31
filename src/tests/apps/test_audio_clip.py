"""
Unit tests for audio-clip (engine + CLI entry point).

All tests use a synthetic 5-second 48 kHz mono sine WAV generated in a
temporary directory — no real hardware or network required.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import io
import sys
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import soundfile as sf

from umik_base_app.apps.audio_clip import main as clip_main
from umik_base_app.apps.audio_clip_engine import (
    clip_audio,
    default_output_path,
    format_time,
    load_audio,
    region_to_wav_bytes,
    validate_range,
    waveform_envelope,
)

# ── Constants ──────────────────────────────────────────────────────────────────

SOURCE_SR = 48_000
SOURCE_DURATION = 5.0
SOURCE_SAMPLES = int(SOURCE_SR * SOURCE_DURATION)


# ── Fixtures ───────────────────────────────────────────────────────────────────


@pytest.fixture
def wav_file(tmp_path: Path) -> Path:
    """5-second 440 Hz sine wave at 48 kHz, PCM_16 mono."""
    t = np.linspace(0, SOURCE_DURATION, SOURCE_SAMPLES, endpoint=False)
    audio = (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)
    path = tmp_path / "test_audio.wav"
    sf.write(str(path), audio, SOURCE_SR, subtype="PCM_16")
    return path


# ── format_time ────────────────────────────────────────────────────────────────


def test_format_time_whole_number():
    assert format_time(5.0) == "5s"
    assert format_time(0.0) == "0s"
    assert format_time(12.0) == "12s"


def test_format_time_fractional():
    assert format_time(5.5) == "5.5s"
    assert format_time(0.1) == "0.1s"


# ── default_output_path ────────────────────────────────────────────────────────


def test_default_output_path_whole_seconds():
    result = default_output_path("recordings/bark.wav", 4.0, 7.0)
    assert result == str(Path("recordings/clips/bark_4s_7s.wav"))


def test_default_output_path_fractional_seconds():
    result = default_output_path("recordings/event.wav", 4.5, 7.2)
    assert result == str(Path("recordings/clips/event_4.5s_7.2s.wav"))


def test_default_output_path_nested_input():
    result = default_output_path("/data/runs/session/noise.wav", 0.0, 3.0)
    assert result.endswith("clips/noise_0s_3s.wav")


# ── validate_range ─────────────────────────────────────────────────────────────


def test_validate_range_valid():
    validate_range(1.0, 4.0, 5.0)  # should not raise


def test_validate_range_start_negative():
    with pytest.raises(ValueError, match="--start"):
        validate_range(-0.1, 4.0, 5.0)


def test_validate_range_start_equals_end():
    with pytest.raises(ValueError, match="must be less than"):
        validate_range(3.0, 3.0, 5.0)


def test_validate_range_end_exceeds_duration():
    with pytest.raises(ValueError, match="exceeds file duration"):
        validate_range(0.0, 6.0, 5.0)


# ── clip_audio — happy path ────────────────────────────────────────────────────


def test_clip_happy_path(wav_file: Path, tmp_path: Path):
    """Clip seconds 1–4; output file length should be 3 × SR samples."""
    start, end = 1.0, 4.0
    out = str(tmp_path / "out.wav")
    result = clip_audio(str(wav_file), start, end, out)

    assert Path(result).exists()
    samples, sr = sf.read(result)
    expected = int((end - start) * SOURCE_SR)
    assert abs(len(samples) - expected) <= 1, f"Expected ~{expected} samples, got {len(samples)}"
    assert sr == SOURCE_SR


def test_clip_default_output_path(wav_file: Path):
    """Without --output the clip lands in <input_dir>/clips/."""
    result = clip_audio(str(wav_file), 2.0, 3.0)
    assert Path(result).exists()
    assert "clips" in result
    assert "2s_3s" in result


def test_clip_duration_option(wav_file: Path, tmp_path: Path):
    """start + duration gives the correct end time."""
    start, dur = 1.0, 2.5
    out = str(tmp_path / "dur.wav")
    result = clip_audio(str(wav_file), start, start + dur, out)
    samples, _ = sf.read(result)
    expected = int(dur * SOURCE_SR)
    assert abs(len(samples) - expected) <= 1


def test_clip_start_gte_end_raises(wav_file: Path):
    """start >= end must raise ValueError."""
    with pytest.raises(ValueError, match="must be less than"):
        clip_audio(str(wav_file), 3.0, 2.0)


def test_clip_end_exceeds_duration_raises(wav_file: Path):
    """end > file duration must raise ValueError."""
    with pytest.raises(ValueError, match="exceeds file duration"):
        clip_audio(str(wav_file), 0.0, 99.0)


def test_clip_source_not_found(tmp_path: Path):
    """Missing source raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        clip_audio(str(tmp_path / "ghost.wav"), 0.0, 1.0)


def test_clip_resample(wav_file: Path, tmp_path: Path):
    """--sr resamples to the target rate and adjusts the sample count."""
    target_sr = 22_050
    out = str(tmp_path / "resampled.wav")
    clip_audio(str(wav_file), 0.0, 2.0, out, target_sr=target_sr)
    samples, sr = sf.read(out)
    assert sr == target_sr
    expected = int(2.0 * target_sr)
    assert abs(len(samples) - expected) <= 5  # librosa may be off by a few


def test_clip_creates_parent_dirs(wav_file: Path, tmp_path: Path):
    """Output path with nested non-existent dirs is created automatically."""
    out = str(tmp_path / "deep" / "nested" / "clip.wav")
    result = clip_audio(str(wav_file), 0.5, 1.5, out)
    assert Path(result).exists()


# ── CLI entry point ────────────────────────────────────────────────────────────


def test_cli_end_and_duration_mutually_exclusive(wav_file: Path, capsys):
    """Passing both --end and --duration should cause argparse to exit."""
    from umik_base_app.apps.audio_clip import main

    sys.argv = ["audio-clip", str(wav_file), "--end", "3", "--duration", "2"]
    with pytest.raises(SystemExit):
        main()


def test_cli_start_gte_end_exits_1(wav_file: Path, capsys):
    """start >= end exits with code 1."""
    from umik_base_app.apps.audio_clip import main

    sys.argv = ["audio-clip", str(wav_file), "--start", "4", "--end", "2"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


def test_cli_end_exceeds_duration_exits_1(wav_file: Path, capsys):
    """end > duration exits with code 1."""
    from umik_base_app.apps.audio_clip import main

    sys.argv = ["audio-clip", str(wav_file), "--end", "999"]
    with pytest.raises(SystemExit) as exc_info:
        main()
    assert exc_info.value.code == 1


# ── waveform_envelope ──────────────────────────────────────────────────────────


def test_waveform_envelope_length(wav_file: Path):
    samples, _, _ = load_audio(str(wav_file))
    envelope = waveform_envelope(samples, n_points=200)
    assert len(envelope) == 200


def test_waveform_envelope_keys(wav_file: Path):
    samples, _, _ = load_audio(str(wav_file))
    envelope = waveform_envelope(samples, n_points=10)
    for point in envelope:
        assert "min" in point and "max" in point
        assert point["min"] <= point["max"]


def test_waveform_envelope_stereo(tmp_path: Path):
    """Stereo input is mixed to mono; envelope still has correct length."""
    n = 48_000
    stereo = np.random.uniform(-0.5, 0.5, (n, 2)).astype(np.float32)
    path = tmp_path / "stereo.wav"
    sf.write(str(path), stereo, 48_000)
    samples, _, _ = load_audio(str(path))
    envelope = waveform_envelope(samples, n_points=100)
    assert len(envelope) == 100


def test_waveform_envelope_empty_samples():
    """Empty sample array returns an empty list without error."""
    assert waveform_envelope(np.array([])) == []


# ── load_audio error path ──────────────────────────────────────────────────────


def test_load_audio_corrupt_file_raises_runtime_error(tmp_path: Path):
    """A file that exists but is not valid audio raises RuntimeError."""
    bad = tmp_path / "corrupt.wav"
    bad.write_bytes(b"this is definitely not a wav file")
    with pytest.raises(RuntimeError, match="Cannot read"):
        load_audio(str(bad))


# ── clip_audio: end=None ───────────────────────────────────────────────────────


def test_clip_end_none_clips_to_end_of_file(wav_file: Path, tmp_path: Path):
    """clip_audio with end=None clips from start to the end of the file."""
    out = str(tmp_path / "full.wav")
    result = clip_audio(str(wav_file), 2.0, None, out)
    samples, sr = sf.read(result)
    expected = int((SOURCE_DURATION - 2.0) * SOURCE_SR)
    assert abs(len(samples) - expected) <= 1


# ── region_to_wav_bytes ────────────────────────────────────────────────────────


def test_region_to_wav_bytes_returns_valid_wav(wav_file: Path):
    """region_to_wav_bytes produces parseable WAV bytes of the correct length."""
    samples, sr, subtype = load_audio(str(wav_file))
    data = region_to_wav_bytes(samples, sr, subtype, 1.0, 2.0)
    out, sr_out = sf.read(io.BytesIO(data))
    assert sr_out == sr
    assert abs(len(out) - sr) <= 1


def test_region_to_wav_bytes_unknown_subtype_falls_back_to_pcm16(wav_file: Path):
    """Subtypes not writable as WAV fall back to PCM_16 rather than erroring."""
    samples, sr, _ = load_audio(str(wav_file))
    data = region_to_wav_bytes(samples, sr, "ALAW", 0.0, 1.0)
    assert data[:4] == b"RIFF"
    _, sr_out = sf.read(io.BytesIO(data))
    assert sr_out == sr


# ── stereo resampling (multi-channel _resample branch) ────────────────────────


def test_clip_resample_stereo_preserves_channels(tmp_path: Path):
    """Resampling a stereo file produces a stereo output at the target rate."""
    sr_in, n = 48_000, 96_000
    stereo = np.zeros((n, 2), dtype=np.float32)
    src = tmp_path / "stereo.wav"
    sf.write(str(src), stereo, sr_in, subtype="PCM_16")
    out = str(tmp_path / "stereo_resampled.wav")
    clip_audio(str(src), 0.0, 1.0, out, target_sr=22_050)
    samples, sr_out = sf.read(out)
    assert sr_out == 22_050
    assert samples.ndim == 2


# ── audio_clip CLI main() ──────────────────────────────────────────────────────


def test_cli_duration_flag_sets_end(wav_file: Path, tmp_path: Path, capsys):
    """--duration N clips exactly N seconds starting from --start."""
    out = str(tmp_path / "dur.wav")
    with patch("sys.argv", ["audio-clip", str(wav_file), "--start", "1.0", "--duration", "2.0", "--output", out]):
        clip_main()
    samples, _ = sf.read(out)
    assert abs(len(samples) - 2 * SOURCE_SR) <= 1
    assert "Clipped" in capsys.readouterr().out


def test_cli_no_end_clips_to_file_end(wav_file: Path, tmp_path: Path, capsys):
    """Omitting --end reads the file duration and clips to end of file."""
    out = str(tmp_path / "toend.wav")
    with patch("sys.argv", ["audio-clip", str(wav_file), "--start", "3.0", "--output", out]):
        clip_main()
    samples, _ = sf.read(out)
    assert abs(len(samples) - int(2.0 * SOURCE_SR)) <= 1
    assert "Clipped" in capsys.readouterr().out


def test_cli_missing_file_no_end_exits_1(tmp_path: Path, capsys):
    """Missing file with no --end hits the load-for-duration path and exits 1."""
    with patch("sys.argv", ["audio-clip", str(tmp_path / "ghost.wav")]):
        with pytest.raises(SystemExit) as exc:
            clip_main()
    assert exc.value.code == 1
    assert "error" in capsys.readouterr().err.lower()
