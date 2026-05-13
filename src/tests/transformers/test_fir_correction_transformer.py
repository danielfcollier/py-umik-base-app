"""
Unit tests for FirCorrectionTransformer.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import MagicMock, patch, sentinel

import numpy as np
import pytest

from umik_base_app.transformers.fir_correction_transformer import (
    FirCorrectionTransformer,
)


@pytest.fixture
def simple_taps():
    """Simple FIR taps for testing (passthrough-ish)."""
    # Simple averaging filter: [0.5, 0.5]
    return np.array([0.5, 0.5], dtype=np.float64)


def test_fir_transformer_applies_filter(simple_taps):
    """Test that FIR filter is applied to audio."""
    transformer = FirCorrectionTransformer(filter_taps=simple_taps)

    # Input: [1, 0, 0, 0]
    # With [0.5, 0.5] filter: output[n] = 0.5*x[n] + 0.5*x[n-1]
    # Expected (with zero initial state): [0.5, 0.5, 0, 0]
    audio = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    result = transformer.process_audio(audio)

    expected = np.array([0.5, 0.5, 0.0, 0.0], dtype=np.float32)
    np.testing.assert_array_almost_equal(result, expected)


def test_fir_transformer_maintains_state_across_chunks(simple_taps):
    """Test that filter state persists between process_audio calls."""
    transformer = FirCorrectionTransformer(filter_taps=simple_taps)

    # First chunk ends with 1.0
    chunk1 = np.array([0.0, 0.0, 1.0], dtype=np.float32)
    transformer.process_audio(chunk1)

    # Second chunk starts with 0.0, but state carries the 1.0
    chunk2 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    result2 = transformer.process_audio(chunk2)

    # First sample of result2 should include contribution from chunk1's last sample
    # With [0.5, 0.5]: result2[0] = 0.5*0.0 + 0.5*1.0 = 0.5
    assert result2[0] == pytest.approx(0.5, abs=1e-6)


def test_fir_transformer_reset_state(simple_taps):
    """Test that reset_state clears filter memory."""
    transformer = FirCorrectionTransformer(filter_taps=simple_taps)

    # Process a chunk to populate state
    chunk1 = np.array([1.0, 1.0, 1.0], dtype=np.float32)
    transformer.process_audio(chunk1)

    # Reset state
    transformer.reset_state()

    # Now process zeros - should get zeros (no state carryover)
    chunk2 = np.array([0.0, 0.0, 0.0], dtype=np.float32)
    result = transformer.process_audio(chunk2)

    expected = np.zeros(3, dtype=np.float32)
    np.testing.assert_array_almost_equal(result, expected)


def test_fir_transformer_preserves_dtype(simple_taps):
    """Test that output dtype matches input dtype."""
    transformer = FirCorrectionTransformer(filter_taps=simple_taps)

    audio_f32 = np.array([0.5, 0.5], dtype=np.float32)
    result = transformer.process_audio(audio_f32)

    assert result.dtype == np.float32


def test_fir_transformer_exposes_properties(simple_taps):
    """Test that filter taps and num_taps are accessible."""
    transformer = FirCorrectionTransformer(filter_taps=simple_taps)

    np.testing.assert_array_equal(transformer.filter_taps, simple_taps)
    assert transformer.num_taps == len(simple_taps)


@patch("umik_base_app.transformers.fir_correction_transformer.lfilter")
def test_fir_transformer_calls_lfilter_correctly(mock_lfilter):
    """Test that lfilter is called with correct arguments."""
    taps = np.array([0.25, 0.5, 0.25])
    transformer = FirCorrectionTransformer(filter_taps=taps)

    mock_output = MagicMock()
    mock_output.dtype = "float32"
    mock_lfilter.return_value = (mock_output, sentinel.new_state)

    audio = MagicMock()
    audio.dtype = "float32"

    transformer.process_audio(audio)

    mock_lfilter.assert_called_once()
    args, kwargs = mock_lfilter.call_args

    np.testing.assert_array_equal(args[0], taps)  # b (taps)
    assert args[1] == 1.0  # a
    assert args[2] is audio  # input
    assert "zi" in kwargs  # state provided
