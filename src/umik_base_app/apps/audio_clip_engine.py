"""
Shared engine for audio-clip and audio-tools-clip.

Handles loading, validation, slicing, optional resampling, and writing of WAV
files. Raises exceptions on all error conditions so that callers (CLI or browser
server) can decide how to report them.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from __future__ import annotations

import io
import logging
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

logger = logging.getLogger(__name__)

WAV_DISPLAY_POINTS = 4_000  # envelope resolution sent to the browser

_WRITABLE_WAV_SUBTYPES: frozenset[str] = frozenset(
    {"PCM_U8", "PCM_16", "PCM_24", "PCM_32", "PCM_S8", "FLOAT", "DOUBLE"}
)


def format_time(t: float) -> str:
    """Return ``'5s'`` for whole seconds, ``'5.5s'`` for fractional (one decimal)."""
    return f"{int(t)}s" if t == int(t) else f"{t:.1f}s"


def default_output_path(input_path: str, start: float, end: float) -> str:
    """Return ``<input_dir>/clips/<stem>_<start>s_<end>s.wav``."""
    p = Path(input_path)
    name = f"{p.stem}_{format_time(start)}_{format_time(end)}.wav"
    return str(p.parent / "clips" / name)


def load_audio(path: str) -> tuple[np.ndarray, int, str]:
    """Load a WAV file and return ``(samples, sample_rate, subtype)``.

    Samples are always ``float64`` in ``[-1, 1]``, shaped ``(n,)`` for mono or
    ``(n, channels)`` for multi-channel. Raises :exc:`FileNotFoundError` if the
    file does not exist, :exc:`RuntimeError` on read errors.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Source file not found: {path}")
    try:
        info = sf.info(str(p))
        samples, sr = sf.read(str(p), dtype="float64", always_2d=False)
    except Exception as exc:
        raise RuntimeError(f"Cannot read '{path}': {exc}") from exc
    return samples, sr, info.subtype


def validate_range(start: float, end: float, duration: float) -> None:
    """Raise :exc:`ValueError` if the requested range is invalid.

    Enforces ``0 <= start < end <= duration``.
    """
    if start < 0:
        raise ValueError(f"--start must be >= 0, got {start:.3f}s")
    if start >= end:
        raise ValueError(f"--start ({start:.3f}s) must be less than --end ({end:.3f}s)")
    if end > duration:
        raise ValueError(f"--end ({end:.3f}s) exceeds file duration ({duration:.3f}s)")


def clip_audio(
    input_path: str,
    start: float,
    end: float | None = None,
    output_path: str | None = None,
    target_sr: int | None = None,
) -> str:
    """Full clip pipeline: load → validate → slice → resample → write.

    :param input_path: Source WAV file path.
    :param start: Clip start in seconds.
    :param end: Clip end in seconds. ``None`` means end of file.
    :param output_path: Destination path. Defaults to
        ``<input_dir>/clips/<stem>_<start>s_<end>s.wav``.
    :param target_sr: Output sample rate. ``None`` preserves the source rate.
    :returns: The resolved output path.
    :raises FileNotFoundError: Source file not found.
    :raises ValueError: Invalid time range.
    """
    samples, sr, subtype = load_audio(input_path)
    n_samples = samples.shape[0] if samples.ndim > 1 else len(samples)
    duration = n_samples / sr

    if end is None:
        end = duration

    validate_range(start, end, duration)

    start_sample = int(start * sr)
    end_sample = int(end * sr)
    chunk = samples[start_sample:end_sample]

    if target_sr is not None and target_sr != sr:
        chunk = _resample(chunk, sr, target_sr)
        sr = target_sr

    out = output_path or default_output_path(input_path, start, end)
    out_p = Path(out)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    write_subtype = subtype if subtype in _WRITABLE_WAV_SUBTYPES else "PCM_16"
    sf.write(str(out_p), chunk, sr, subtype=write_subtype)
    logger.info("Clipped %.2fs → %s", end - start, out)
    return out


def waveform_envelope(samples: np.ndarray, n_points: int = WAV_DISPLAY_POINTS) -> list[dict[str, float]]:
    """Return a min/max envelope of *samples* downsampled to *n_points* blocks.

    Mixes multi-channel audio to mono before computing the envelope. The result
    is a list of ``{"min": float, "max": float}`` dicts suitable for JSON.
    """
    mono: np.ndarray = samples if samples.ndim == 1 else samples.mean(axis=1)
    n = len(mono)
    if n == 0:
        return []
    block_size = max(1, n // n_points)
    trim = (n // block_size) * block_size
    blocks = mono[:trim].reshape(-1, block_size)
    mins = blocks.min(axis=1)
    maxs = blocks.max(axis=1)
    return [{"min": round(float(mn), 5), "max": round(float(mx), 5)} for mn, mx in zip(mins, maxs)]


def region_to_wav_bytes(samples: np.ndarray, sr: int, subtype: str, start: float, end: float) -> bytes:
    """Clip *samples* to ``[start, end]`` and return the result as WAV bytes.

    Clamps *start* and *end* to valid sample bounds — intended for the HTTP
    preview endpoint where the client may send slightly-out-of-range values.
    """
    duration = samples.shape[0] / sr
    start = max(0.0, min(start, duration))
    end = max(start, min(end, duration))
    chunk = samples[int(start * sr) : int(end * sr)]
    write_subtype = subtype if subtype in _WRITABLE_WAV_SUBTYPES else "PCM_16"
    buf = io.BytesIO()
    sf.write(buf, chunk, sr, subtype=write_subtype, format="WAV")
    return buf.getvalue()


def _resample(chunk: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    """Resample *chunk* (mono or multi-channel) using librosa."""
    data = chunk.astype(np.float32)
    if data.ndim == 1:
        out = librosa.resample(data, orig_sr=orig_sr, target_sr=target_sr)
    else:
        # soundfile gives (n_samples, n_channels); librosa expects (n_channels, n_samples)
        out = librosa.resample(data.T, orig_sr=orig_sr, target_sr=target_sr).T
    return out.astype(np.float64)
