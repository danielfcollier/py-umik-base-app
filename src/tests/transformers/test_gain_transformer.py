"""
Unit tests for GainTransformer.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import numpy as np

from umik_base_app.transformers.gain_transformer import GainTransformer


def test_gain_transformer_applies_gain():
    """Test that gain is applied correctly to audio samples."""
    gain = 2.0
    transformer = GainTransformer(gain_linear=gain)

    audio = np.array([0.5, -0.5, 0.25], dtype=np.float32)
    result = transformer.process_audio(audio)

    expected = np.array([1.0, -1.0, 0.5], dtype=np.float32)
    np.testing.assert_array_almost_equal(result, expected)


def test_gain_transformer_unity_gain():
    """Test that unity gain (1.0) passes audio unchanged."""
    transformer = GainTransformer(gain_linear=1.0)

    audio = np.array([0.1, 0.2, 0.3], dtype=np.float32)
    result = transformer.process_audio(audio)

    np.testing.assert_array_equal(result, audio)


def test_gain_transformer_zero_gain():
    """Test that zero gain produces silence."""
    transformer = GainTransformer(gain_linear=0.0)

    audio = np.array([0.5, -0.5, 1.0], dtype=np.float32)
    result = transformer.process_audio(audio)

    expected = np.zeros(3, dtype=np.float32)
    np.testing.assert_array_equal(result, expected)


def test_gain_transformer_is_stateless():
    """Test that transformer produces same output for same input."""
    transformer = GainTransformer(gain_linear=2.0)

    audio = np.array([0.5, 0.5, 0.5], dtype=np.float32)

    result1 = transformer.process_audio(audio)
    result2 = transformer.process_audio(audio)

    np.testing.assert_array_equal(result1, result2)


def test_gain_transformer_exposes_gain_property():
    """Test that gain value is accessible via property."""
    gain = 1.5
    transformer = GainTransformer(gain_linear=gain)

    assert transformer.gain == gain
