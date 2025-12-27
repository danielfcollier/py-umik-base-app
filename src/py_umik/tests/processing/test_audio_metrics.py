"""
Unit tests for the AudioMetrics class.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import patch

import numpy as np
import pytest

from py_umik.processing.audio_metrics import AudioMetrics
from py_umik.settings import get_settings

settings = get_settings()

# Constants for testing
SAMPLE_RATE = 48000


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


# ... (Existing tests for RMS, dBFS, dBSPL remain here) ...


def test_flux(metrics):
    """Test that flux calls librosa and returns the max value."""
    # Mock librosa to avoid actual DSP calculation
    with patch("py_umik.processing.audio_metrics.librosa.onset.onset_strength") as mock_onset:
        # Return a dummy envelope with a known max
        mock_onset.return_value = np.array([0.1, 0.5, 0.2])

        chunk = np.zeros(1024)
        result = metrics.flux(chunk, SAMPLE_RATE)

        assert result == 0.5
        mock_onset.assert_called_once()


def test_lufs_aggregation(metrics):
    """Test adding chunks and retrieving/clearing them."""
    chunk1 = np.array([0.1, 0.2])
    chunk2 = np.array([0.3, 0.4])

    # 1. Add chunks
    metrics.aggregate_lufs_chunks(chunk1)
    metrics.aggregate_lufs_chunks(chunk2)

    # 2. Verify internal state (white-box testing)
    assert len(metrics._lufs_chunks) == 2

    # 3. Retrieve chunks
    retrieved = metrics.get_lufs_chunks()

    # 4. Verify retrieval and clearing
    assert len(retrieved) == 2
    assert np.array_equal(retrieved[0], chunk1)
    assert np.array_equal(retrieved[1], chunk2)
    assert len(metrics._lufs_chunks) == 0  # Should be cleared


def test_show_metrics(metrics):
    """Test that show_metrics logs the correct formatted string."""
    with patch("py_umik.processing.audio_metrics.logger") as mock_logger:
        # Pass arbitrary metrics
        metrics.show_metrics(measured_at="12:00:00", rms=0.123456, dbfs=-20.5)

        # Check if logger was called
        mock_logger.info.assert_called_once()

        # Verify formatting (only 4 decimals)
        log_message = mock_logger.info.call_args[0][0]
        assert "0.1235" in log_message  # Rounded up
        assert "-20.5000" in log_message
        assert "measured_at: 12:00:00" in log_message
