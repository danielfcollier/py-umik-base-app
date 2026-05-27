"""
Unit tests for the AudioMetrics class.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import patch, sentinel

import numpy as np
import pytest

from umik_base_app import AudioMetrics
from umik_base_app.settings import get_settings

settings = get_settings()

# Constants for testing
SAMPLE_RATE = 48000
SENSITIVITY = -18.0  # dBFS  (typical UMIK-1 sensitivity)
REFERENCE = 94.0  # dBSPL (standard 1 Pa reference)


def _sine(freq_hz: float, duration_s: float = 0.5) -> np.ndarray:
    """Return a pure sine wave long enough for filter transients to settle."""
    t = np.linspace(0, duration_s, int(SAMPLE_RATE * duration_s), endpoint=False)
    return np.sin(2 * np.pi * freq_hz * t).astype(np.float32)


@pytest.fixture(autouse=True)
def mock_settings():
    """Overrides settings to ensure deterministic test results."""
    settings.METRICS.DBFS_LOWER_BOUND = -120.0
    settings.METRICS.LUFS_LOWER_BOUND = -120.0
    settings.AUDIO.LUFS_WINDOW_SECONDS = 3


@pytest.fixture
def metrics():
    """Returns an AudioMetrics instance."""
    return AudioMetrics(sample_rate=SAMPLE_RATE)


def test_flux(metrics):
    """Test that flux calls librosa and returns the max value."""
    # Mock librosa to avoid actual DSP calculation
    with patch("umik_base_app.core.audio_metrics.librosa.onset.onset_strength") as mock_onset:
        # We also need to mock np.max if we want to avoid real math,
        # OR we can just return a real array and let np.max work.
        # Using a real array is cleaner for 'max' logic, but we can verify the call arguments with sentinel.
        mock_onset.return_value = [0.1, 0.5, 0.2]

        result = metrics.flux(sentinel.chunk, SAMPLE_RATE)

        assert result == 0.5
        mock_onset.assert_called_once_with(y=sentinel.chunk, sr=SAMPLE_RATE)


def test_lufs_aggregation(metrics):
    """Test adding chunks and retrieving/clearing them."""
    # 1. Add sentinel chunks
    metrics.aggregate_lufs_chunks(sentinel.chunk1)
    metrics.aggregate_lufs_chunks(sentinel.chunk2)

    # 2. Verify internal state (white-box testing)
    assert len(metrics._lufs_chunks) == 2
    assert metrics._lufs_chunks[0] is sentinel.chunk1

    # 3. Retrieve chunks
    retrieved = metrics.get_lufs_chunks()

    # 4. Verify retrieval and clearing
    assert len(retrieved) == 2
    assert retrieved[0] is sentinel.chunk1
    assert retrieved[1] is sentinel.chunk2
    assert len(metrics._lufs_chunks) == 0  # Should be cleared


# ── dBSPL_A ───────────────────────────────────────────────────────────────────


def test_dbspl_a_1khz_matches_dbspl(metrics):
    """At 1 kHz A-weighting gain is 0 dB, so dBSPL_A ≈ dBSPL."""
    chunk = _sine(1000.0)
    dbspl = metrics.dBSPL(metrics.dBFS(chunk), SENSITIVITY, REFERENCE)
    dbspl_a = metrics.dBSPL_A(chunk, SENSITIVITY, REFERENCE)
    assert abs(dbspl_a - dbspl) < 0.5


def test_dbspl_a_100hz_attenuated(metrics):
    """At 100 Hz A-weighting attenuates by ~19 dB, so dBSPL_A << dBSPL."""
    chunk = _sine(100.0)
    dbspl = metrics.dBSPL(metrics.dBFS(chunk), SENSITIVITY, REFERENCE)
    dbspl_a = metrics.dBSPL_A(chunk, SENSITIVITY, REFERENCE)
    # IEC 61672 reference attenuation at 100 Hz: −19.1 dB
    assert 17.0 < (dbspl - dbspl_a) < 21.0


def test_dbspl_a_applies_calibration_offset(metrics):
    """Calibration sensitivity and reference shift are applied to the A-weighted level."""
    chunk = _sine(1000.0)
    dbfs_a = metrics._dBFS_A(chunk)
    expected = dbfs_a - SENSITIVITY + REFERENCE
    assert abs(metrics.dBSPL_A(chunk, SENSITIVITY, REFERENCE) - expected) < 1e-6


def test_dbspl_a_stereo_input(metrics):
    """Stereo (N, 2) input is mixed to mono and processed without error."""
    mono = _sine(1000.0)
    stereo = np.stack([mono, mono], axis=1)
    result = metrics.dBSPL_A(stereo, SENSITIVITY, REFERENCE)
    assert isinstance(result, float)


# ── L_Aeq ─────────────────────────────────────────────────────────────────────


def test_l_aeq_uniform_samples():
    """All identical samples → L_Aeq equals that level exactly."""
    assert abs(AudioMetrics.L_Aeq([75.0] * 100) - 75.0) < 1e-6


def test_l_aeq_energy_average_not_arithmetic():
    """L_Aeq is energy-based, not the arithmetic mean of the dB values."""
    result = AudioMetrics.L_Aeq([90.0, 80.0])
    # Energy average: 10*log10((10^9 + 10^8) / 2) ≈ 87.4 dB
    assert abs(result - 87.4) < 0.1
    assert result != 85.0  # arithmetic mean would be 85.0


def test_l_aeq_single_sample():
    """A single sample → L_Aeq equals that sample."""
    assert abs(AudioMetrics.L_Aeq([83.5]) - 83.5) < 1e-6


def test_l_aeq_accepts_list():
    """Accepts a plain Python list."""
    assert isinstance(AudioMetrics.L_Aeq([60.0, 65.0, 70.0]), float)


def test_l_aeq_accepts_numpy_array():
    """Accepts a numpy array."""
    assert isinstance(AudioMetrics.L_Aeq(np.array([60.0, 65.0, 70.0])), float)


def test_l_aeq_loud_event_dominates():
    """A single loud event raises L_Aeq significantly above the quiet baseline."""
    quiet = [50.0] * 99
    loud = [90.0]
    # 10*log10((99*10^5 + 10^9) / 100) ≈ 70 dB — dominated by the 90 dB event
    assert AudioMetrics.L_Aeq(quiet + loud) > 70.0


# ── L_A90 ─────────────────────────────────────────────────────────────────────


def test_l_a90_uniform_samples():
    """All identical samples → L_A90 equals that level."""
    assert abs(AudioMetrics.L_A90([65.0] * 100) - 65.0) < 1e-6


def test_l_a90_is_tenth_percentile():
    """L_A90 is the 10th percentile of the sample distribution."""
    samples = list(range(100))  # 0, 1, …, 99
    # numpy 10th percentile of 0-99 = 9.9
    assert abs(AudioMetrics.L_A90(samples) - 9.9) < 0.1


def test_l_a90_always_le_l_aeq():
    """L_A90 ≤ L_Aeq,T for any sample set (background ≤ energy average)."""
    samples = [50.0, 60.0, 70.0, 80.0, 90.0]
    assert AudioMetrics.L_A90(samples) <= AudioMetrics.L_Aeq(samples)


def test_l_a90_accepts_numpy_array():
    """Accepts a numpy array as input."""
    result = AudioMetrics.L_A90(np.array([55.0, 65.0, 75.0]))
    assert isinstance(result, float)


# ── show_metrics ───────────────────────────────────────────────────────────────


def test_show_metrics(metrics):
    """Test that show_metrics logs the correct formatted string."""
    with patch("umik_base_app.core.audio_metrics.logger") as mock_logger:
        # Pass arbitrary metrics
        metrics.show_metrics(measured_at="12:00:00", rms=0.123456, dbfs=-20.5)

        # Check if logger was called
        mock_logger.info.assert_called_once()

        # Verify formatting (only 4 decimals)
        log_message = mock_logger.info.call_args[0][0]
        assert "0.1235" in log_message  # Rounded up
        assert "-20.5000" in log_message
        assert "measured_at: 12:00:00" in log_message
