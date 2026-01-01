"""
Unit tests for the AudioMetrics class.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import patch, sentinel

import pytest

from umik_base_app import AudioMetrics
from umik_base_app.settings import get_settings

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
