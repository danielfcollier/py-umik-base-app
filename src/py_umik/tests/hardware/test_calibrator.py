"""
Unit tests for the HardwareCalibrator class.
Uses mocking to avoid file I/O and verify filter design logic.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import mock_open, patch

import numpy as np
import pytest

from py_umik.hardware.cache_strategy import NoOpFilterCache
from py_umik.hardware.calibrator import HardwareCalibrator
from py_umik.settings import get_settings

settings = get_settings()


DUMMY_CAL_DATA = """
"Sens Factor" =-1.23dB, SERNO: 7000000
10.00	-5.0
20.00	-2.5
1000.00	0.0
10000.00 1.5
20000.00 2.0
"""


@pytest.fixture(autouse=True)
def mock_settings():
    """
    Ensure settings are in a known state for all tests.
    """
    settings.AUDIO.NUM_TAPS = 1024
    settings.AUDIO.SAMPLE_RATE = 48000
    settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS = -18.0
    settings.HARDWARE.REFERENCE_DBSPL = 94.0


@pytest.fixture
def mock_firwin2():
    """
    Mocks scipy.signal.firwin2 to avoid complex DSP calculations during tests.
    Returns a simple impulse response (identity filter).
    """
    with patch("py_umik.hardware.calibrator.firwin2") as mock:
        # Create a mock filter array.
        # HardwareCalibrator designs a filter of length `num_taps`.
        # firwin2 returns `numtaps` coefficients.
        # The code calls firwin2 with (num_taps - 1), so we return that many.

        def side_effect(ntaps, freqs, gains, **kwargs):
            return np.ones(ntaps)  # Return dummy ones

        mock.side_effect = side_effect
        yield mock


def test_initialization_parses_file_and_designs_filter(mock_firwin2):
    """
    Verify that initialization reads the file, parses frequencies,
    calls the filter design function, and does NOT crash.
    """
    # Mock 'open' to read our dummy string instead of a real file
    with patch("builtins.open", mock_open(read_data=DUMMY_CAL_DATA)) as mock_file:
        # Initialize HardwareCalibrator with NoOp cache (crucial for isolation)
        calibrator = HardwareCalibrator(
            calibration_file_path="/fake/path/cal.txt",
            sample_rate=48000,
            num_taps=1024,
            cache_strategy=NoOpFilterCache(),
        )

        # 1. Verify file was opened correctly
        mock_file.assert_called_with("/fake/path/cal.txt", encoding="utf-8")

        # 2. Verify firwin2 was called to design the filter
        assert mock_firwin2.called

        # 3. Verify parameters passed to firwin2
        # The call signature is firwin2(num_taps - 1, full_freqs, extrapolated_gains)
        args, _ = mock_firwin2.call_args
        assert args[0] == 1023  # num_taps (1024) - 1

        # 4. Verify internal state is set
        assert calibrator._filter_taps is not None
        assert len(calibrator._filter_taps) == 1023


def test_apply_maintains_shape(mock_firwin2):
    """
    Verify that the apply() method accepts a numpy array and returns
    a calibrated array of the same shape.
    """
    with patch("builtins.open", mock_open(read_data=DUMMY_CAL_DATA)):
        calibrator = HardwareCalibrator(
            calibration_file_path="/fake/path/cal.txt",
            sample_rate=48000,
            num_taps=1024,
            cache_strategy=NoOpFilterCache(),
        )

        # Create a dummy audio chunk (e.g., 100ms at 48k)
        chunk_size = 4800
        input_audio = np.random.uniform(-1.0, 1.0, chunk_size).astype(np.float32)

        # Apply calibration
        output_audio = calibrator.apply(input_audio)

        # Verify output properties
        assert isinstance(output_audio, np.ndarray)
        assert output_audio.shape == input_audio.shape
        assert output_audio.dtype == input_audio.dtype


def test_get_sensitivity_values_parsing():
    """Verify parsing of 'Sens Factor' from file content."""
    dummy_content = "Some Header\nSens Factor =-12.5dB, Other Data\n1000 0.0"

    with patch("builtins.open", mock_open(read_data=dummy_content)):
        # Ensure settings don't interfere with specific math for this test
        settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS = -18.0
        settings.HARDWARE.REFERENCE_DBSPL = 94.0

        sens_dbfs, ref_spl = HardwareCalibrator.get_sensitivity_values("dummy.txt")

        # Calculation: Nominal(-18.0) + Factor(-12.5) = -30.5
        assert sens_dbfs == -30.5
        assert ref_spl == 94.0


def test_get_sensitivity_values_missing_header():
    """Verify error raised when Sens Factor is missing."""
    dummy_content = "Just Freq Data\n1000 0.0"

    with patch("builtins.open", mock_open(read_data=dummy_content)):
        with pytest.raises(ValueError, match="not found"):
            HardwareCalibrator.get_sensitivity_values("dummy.txt")
