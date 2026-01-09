"""
Unit tests for the CalibratorTransformer class.
Uses mocking to avoid file I/O and verify filter design logic.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import MagicMock, mock_open, patch, sentinel

import pytest

from umik_base_app.settings import get_settings
from umik_base_app.transformers.calibrator_cache_strategy import NoOpCalibratorCache
from umik_base_app.transformers.calibrator_transformer import CalibratorTransformer

settings = get_settings()


DUMMY_CAL_DATA = """
"Sens Factor" =-1.23dB, SERNO: 7000000
10.00   -5.0
20.00   -2.5
1000.00 0.0
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
    Mocks scipy.signal.firwin2.
    Returns a MagicMock that supports len() to satisfy initialization logic.
    """
    with patch("umik_base_app.transformers.calibrator_transformer.firwin2") as mock:
        # Create a mock that acts like a list/array of length 1023
        # (num_taps - 1)
        mock_taps = MagicMock()
        mock_taps.__len__.return_value = 1023
        mock.return_value = mock_taps
        yield mock


def test_initialization_parses_file_and_designs_filter(mock_firwin2):
    """
    Verify that initialization reads the file, parses frequencies,
    calls the filter design function, and stores the result.
    """
    # Must use a string path because __init__ uses os.path.dirname/basename
    fake_path = "/fake/path/cal.txt"

    # Mock 'open' to read our dummy string instead of a real file
    with patch("builtins.open", mock_open(read_data=DUMMY_CAL_DATA)) as mock_file:
        # Initialize CalibratorTransformer
        calibrator = CalibratorTransformer(
            calibration_file_path=fake_path,
            sample_rate=48000,
            nominal_sensitivity_dbfs=-18.0,
            reference_dbspl=94.0,
            num_taps=1024,
            cache_strategy=NoOpCalibratorCache(),
        )

        # 1. Verify file was opened
        mock_file.assert_called_with(fake_path, encoding="utf-8")

        # 2. Verify firwin2 was called to design the filter
        assert mock_firwin2.called

        # 3. Verify parameters passed to firwin2
        # The call signature is firwin2(num_taps - 1, full_freqs, extrapolated_gains)
        args, _ = mock_firwin2.call_args
        assert args[0] == 1023  # num_taps (1024) - 1

        # 4. Verify internal state stores the mock returned by firwin2
        assert calibrator._filter_taps == mock_firwin2.return_value


@patch("umik_base_app.transformers.calibrator_transformer.lfilter")
def test_apply_filters_signal(mock_lfilter, mock_firwin2):
    """
    Verify that the apply() method calls lfilter with the
    input audio multiplied by the gain.
    """
    # Create inputs/outputs with .dtype attributes to satisfy type check logic
    # if calibrated_chunk.dtype != audio_chunk.dtype: ...
    mock_input_audio = MagicMock()
    mock_input_audio.dtype = "float32"

    mock_calibrated_chunk = MagicMock()
    mock_calibrated_chunk.dtype = "float32"

    # lfilter returns (y, zf) -> (filtered_data, final_state)
    mock_lfilter.return_value = (mock_calibrated_chunk, sentinel.new_state)

    fake_path = "/fake/path/cal.txt"

    with patch("builtins.open", mock_open(read_data=DUMMY_CAL_DATA)):
        # We use nominal_sensitivity_dbfs = 1.23 to cancel out the -1.23dB "Sens Factor"
        # in DUMMY_CAL_DATA. Result: 0dB gain (1.0x).
        calibrator = CalibratorTransformer(
            calibration_file_path=fake_path,
            sample_rate=48000,
            nominal_sensitivity_dbfs=1.23,
            reference_dbspl=94.0,
            num_taps=1024,
            cache_strategy=NoOpCalibratorCache(),
        )

        # Apply calibration
        output = calibrator.apply(mock_input_audio)

        # 1. Verify Gain Application
        # The input audio should be multiplied by the gain (1.0 in this specific setup)
        mock_input_audio.__mul__.assert_called_with(1.0)
        expected_gained_chunk = mock_input_audio.__mul__.return_value

        # 2. Verify lfilter was called with the GAINED chunk
        mock_lfilter.assert_called_once()
        args, kwargs = mock_lfilter.call_args

        # Expected: lfilter(b, a, x, zi=...)
        assert args[0] == mock_firwin2.return_value  # b (taps)
        assert args[1] == 1.0  # a
        assert args[2] == expected_gained_chunk  # x (MUST BE THE MULTIPLIED OBJECT)
        assert "zi" in kwargs  # zi (state provided)

        # 3. Verify output matches
        assert output == mock_calibrated_chunk

        # 4. Verify internal state update
        assert calibrator._filter_state == sentinel.new_state


def test_apply_resets_state(mock_firwin2):
    """
    Verify that calling apply(reset_state=True) resets the internal filter state.
    """
    fake_path = "/fake/path/cal.txt"
    mock_input_audio = MagicMock()
    mock_input_audio.dtype = "float32"

    with patch("builtins.open", mock_open(read_data=DUMMY_CAL_DATA)):
        with patch("umik_base_app.transformers.calibrator_transformer.lfilter") as mock_lfilter:
            # Setup lfilter to return dummy data
            mock_lfilter.return_value = (mock_input_audio, [1, 2, 3])

            calibrator = CalibratorTransformer(
                calibration_file_path=fake_path,
                sample_rate=48000,
                nominal_sensitivity_dbfs=-18.0,
                reference_dbspl=94.0,
                num_taps=1024,
                cache_strategy=NoOpCalibratorCache(),
            )

            # Dirty the state
            calibrator._filter_state = [9, 9, 9]

            # Apply with reset
            calibrator.apply(mock_input_audio, reset_state=True)

            # Check if lfilter received a zeroed state in kwargs
            _, kwargs = mock_lfilter.call_args
            passed_zi = kwargs["zi"]

            # Should be all zeros (float)
            assert (passed_zi == 0).all()


def test_get_sensitivity_values_parsing():
    """Verify parsing of 'Sens Factor' from file content."""
    dummy_content = "Some Header\nSens Factor =-12.5dB, Other Data\n1000 0.0"

    with patch("builtins.open", mock_open(read_data=dummy_content)):
        sens_dbfs, ref_spl = CalibratorTransformer.get_sensitivity_values(
            "dummy.txt", nominal_sensitivity_dbfs=-18.0, reference_dbspl=94.0
        )

        # Calculation: Nominal(-18.0) + Factor(-12.5) = -30.5
        assert sens_dbfs == -30.5
        assert ref_spl == 94.0


def test_get_sensitivity_values_missing_header():
    """Verify error raised when Sens Factor is missing."""
    dummy_content = "Just Freq Data\n1000 0.0"

    with patch("builtins.open", mock_open(read_data=dummy_content)):
        with pytest.raises(ValueError, match="not found"):
            CalibratorTransformer.get_sensitivity_values(
                "dummy.txt", nominal_sensitivity_dbfs=-18.0, reference_dbspl=94.0
            )
