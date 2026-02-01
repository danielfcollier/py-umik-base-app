"""
Unit tests for PipelineContext.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from datetime import datetime

import numpy as np
import pytest

from umik_base_app import PipelineContext


@pytest.fixture
def sample_context():
    """Create a sample PipelineContext for testing."""
    return PipelineContext(
        audio=np.array([0.1, 0.2, 0.3], dtype=np.float32),
        timestamp=datetime(2025, 1, 15, 12, 0, 0),
        sample_rate=48000.0,
    )


class TestPipelineContextCreation:
    """Tests for PipelineContext initialization."""

    def test_create_with_required_fields(self, sample_context):
        """Verify context can be created with required fields."""
        assert len(sample_context.audio) == 3
        assert sample_context.timestamp == datetime(2025, 1, 15, 12, 0, 0)
        assert sample_context.sample_rate == 48000.0
        assert sample_context.metadata == {}

    def test_create_with_metadata(self):
        """Verify context can be created with initial metadata."""
        ctx = PipelineContext(
            audio=np.array([0.0]),
            timestamp=datetime.now(),
            sample_rate=44100.0,
            metadata={"key": "value"},
        )
        assert ctx.metadata == {"key": "value"}


class TestMetadataAccessors:
    """Tests for generic metadata accessors."""

    def test_set_and_get_metadata(self, sample_context):
        """Verify set() and get() work correctly."""
        sample_context.set("test_key", "test_value")
        assert sample_context.get("test_key") == "test_value"

    def test_get_with_default(self, sample_context):
        """Verify get() returns default for missing keys."""
        assert sample_context.get("missing_key") is None
        assert sample_context.get("missing_key", "default") == "default"

    def test_has_metadata(self, sample_context):
        """Verify has() checks key existence."""
        assert sample_context.has("nonexistent") is False
        sample_context.set("exists", True)
        assert sample_context.has("exists") is True

    def test_set_returns_self_for_chaining(self, sample_context):
        """Verify set() returns self for method chaining."""
        result = sample_context.set("key1", "value1")
        assert result is sample_context

        # Chain multiple sets
        sample_context.set("a", 1).set("b", 2).set("c", 3)
        assert sample_context.get("a") == 1
        assert sample_context.get("b") == 2
        assert sample_context.get("c") == 3


class TestTypedAccessors:
    """Tests for typed property accessors."""

    def test_sensitivity_dbfs_default(self, sample_context):
        """Verify sensitivity_dbfs returns None by default."""
        assert sample_context.sensitivity_dbfs is None

    def test_sensitivity_dbfs_set(self, sample_context):
        """Verify sensitivity_dbfs returns set value."""
        sample_context.set("sensitivity_dbfs", -18.5)
        assert sample_context.sensitivity_dbfs == -18.5

    def test_reference_dbspl_default(self, sample_context):
        """Verify reference_dbspl returns None by default."""
        assert sample_context.reference_dbspl is None

    def test_reference_dbspl_set(self, sample_context):
        """Verify reference_dbspl returns set value."""
        sample_context.set("reference_dbspl", 94.0)
        assert sample_context.reference_dbspl == 94.0

    def test_calibration_applied_default(self, sample_context):
        """Verify calibration_applied returns False by default."""
        assert sample_context.calibration_applied is False

    def test_calibration_applied_set(self, sample_context):
        """Verify calibration_applied returns set value."""
        sample_context.set("calibration_applied", True)
        assert sample_context.calibration_applied is True

    def test_gain_applied_default(self, sample_context):
        """Verify gain_applied returns False by default."""
        assert sample_context.gain_applied is False

    def test_gain_applied_set(self, sample_context):
        """Verify gain_applied returns set value."""
        sample_context.set("gain_applied", True)
        assert sample_context.gain_applied is True

    def test_fir_applied_default(self, sample_context):
        """Verify fir_applied returns False by default."""
        assert sample_context.fir_applied is False

    def test_fir_applied_set(self, sample_context):
        """Verify fir_applied returns set value."""
        sample_context.set("fir_applied", True)
        assert sample_context.fir_applied is True


class TestAudioMutability:
    """Tests for audio array mutability."""

    def test_audio_can_be_modified(self, sample_context):
        """Verify audio array can be modified in place."""
        sample_context.audio = sample_context.audio * 2
        expected = np.array([0.2, 0.4, 0.6], dtype=np.float32)
        assert np.allclose(sample_context.audio, expected)

    def test_audio_can_be_replaced(self, sample_context):
        """Verify audio array can be replaced entirely."""
        new_audio = np.array([1.0, 2.0, 3.0, 4.0])
        sample_context.audio = new_audio
        assert np.array_equal(sample_context.audio, new_audio)


class TestCalibrationMetadataPattern:
    """Tests for typical calibration metadata usage patterns."""

    def test_calibration_metadata_workflow(self, sample_context):
        """Verify typical calibration metadata workflow."""
        # Simulate CalibratorAdapter setting metadata
        sample_context.set("calibration_applied", True)
        sample_context.set("sensitivity_dbfs", -18.545)
        sample_context.set("reference_dbspl", 94.0)
        sample_context.set("gain_applied", True)
        sample_context.set("fir_applied", True)

        # Verify sink can read all values
        assert sample_context.calibration_applied is True
        assert sample_context.sensitivity_dbfs == -18.545
        assert sample_context.reference_dbspl == 94.0
        assert sample_context.gain_applied is True
        assert sample_context.fir_applied is True

    def test_uncalibrated_context(self, sample_context):
        """Verify uncalibrated context has correct defaults."""
        # When no calibration is applied, all should be False/None
        assert sample_context.calibration_applied is False
        assert sample_context.sensitivity_dbfs is None
        assert sample_context.reference_dbspl is None
        assert sample_context.gain_applied is False
        assert sample_context.fir_applied is False


class TestCalibrationHelperMethods:
    """Tests for calibration state helper methods."""

    def test_is_gain_calibrated_false_by_default(self, sample_context):
        """Uncalibrated context returns False for is_gain_calibrated."""
        assert sample_context.is_gain_calibrated() is False

    def test_is_gain_calibrated_requires_both_flags(self, sample_context):
        """is_gain_calibrated needs gain_applied AND sensitivity_dbfs."""
        # Only gain_applied - not enough
        sample_context.set("gain_applied", True)
        assert sample_context.is_gain_calibrated() is False

        # Add sensitivity - now it's True
        sample_context.set("sensitivity_dbfs", -18.0)
        assert sample_context.is_gain_calibrated() is True

    def test_is_frequency_calibrated(self, sample_context):
        """is_frequency_calibrated checks fir_applied flag."""
        assert sample_context.is_frequency_calibrated() is False
        sample_context.set("fir_applied", True)
        assert sample_context.is_frequency_calibrated() is True

    def test_is_fully_calibrated(self, sample_context):
        """is_fully_calibrated requires both gain and FIR."""
        assert sample_context.is_fully_calibrated() is False

        # Add gain calibration
        sample_context.set("gain_applied", True)
        sample_context.set("sensitivity_dbfs", -18.0)
        assert sample_context.is_fully_calibrated() is False

        # Add FIR calibration
        sample_context.set("fir_applied", True)
        assert sample_context.is_fully_calibrated() is True

    def test_can_calculate_dbspl(self, sample_context):
        """can_calculate_dbspl needs sensitivity and reference."""
        assert sample_context.can_calculate_dbspl() is False

        # Only sensitivity - not enough
        sample_context.set("sensitivity_dbfs", -18.0)
        assert sample_context.can_calculate_dbspl() is False

        # Add reference - now it's True
        sample_context.set("reference_dbspl", 94.0)
        assert sample_context.can_calculate_dbspl() is True

    def test_get_calibration_summary(self, sample_context):
        """get_calibration_summary returns complete state dict."""
        # Uncalibrated
        summary = sample_context.get_calibration_summary()
        assert summary["gain_applied"] is False
        assert summary["fir_applied"] is False
        assert summary["fully_calibrated"] is False
        assert summary["sensitivity_dbfs"] is None
        assert summary["reference_dbspl"] is None

        # Fully calibrated
        sample_context.set("gain_applied", True)
        sample_context.set("fir_applied", True)
        sample_context.set("sensitivity_dbfs", -18.5)
        sample_context.set("reference_dbspl", 94.0)
        sample_context.set("gain_linear", 8.414)
        sample_context.set("fir_num_taps", 1023)

        summary = sample_context.get_calibration_summary()
        assert summary["gain_applied"] is True
        assert summary["fir_applied"] is True
        assert summary["fully_calibrated"] is True
        assert summary["sensitivity_dbfs"] == -18.5
        assert summary["reference_dbspl"] == 94.0
        assert summary["gain_linear"] == 8.414
        assert summary["fir_num_taps"] == 1023

    def test_gain_linear_and_fir_num_taps_accessors(self, sample_context):
        """Verify gain_linear and fir_num_taps typed accessors."""
        assert sample_context.gain_linear is None
        assert sample_context.fir_num_taps is None

        sample_context.set("gain_linear", 2.5)
        sample_context.set("fir_num_taps", 512)

        assert sample_context.gain_linear == 2.5
        assert sample_context.fir_num_taps == 512
