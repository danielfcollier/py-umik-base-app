"""
Defines the PipelineContext dataclass for carrying audio and metadata through the pipeline.

This module provides the core data structure that flows through the audio processing
pipeline, enabling transformers to annotate metadata and sinks to access both
audio data and processing information without tight coupling to config objects.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np


@dataclass
class PipelineContext:
    """
    Carries audio data and metadata through the processing pipeline.

    Created by AudioPipeline.execute() at the start of processing.
    Transformers receive and return context (may modify in place).
    Sinks receive context for read-only consumption.

    Attributes:
        audio: The audio samples as a numpy array.
        timestamp: When the audio chunk was captured.
        sample_rate: Audio sample rate in Hz.
        metadata: Flexible dict for transformer annotations.
    """

    # Required fields - the core data
    audio: np.ndarray
    timestamp: datetime
    sample_rate: float

    # Flexible metadata store for transformer annotations
    metadata: dict[str, Any] = field(default_factory=dict)

    # --- Generic accessors ---

    def get(self, key: str, default: Any = None) -> Any:
        """
        Read metadata value with optional default.

        :param key: The metadata key to retrieve.
        :param default: Value to return if key is not found.
        :return: The metadata value or default.
        """
        return self.metadata.get(key, default)

    def set(self, key: str, value: Any) -> PipelineContext:
        """
        Set metadata value. Returns self for chaining.

        :param key: The metadata key to set.
        :param value: The value to store.
        :return: Self for method chaining.
        """
        self.metadata[key] = value
        return self

    def has(self, key: str) -> bool:
        """
        Check if metadata key exists.

        :param key: The metadata key to check.
        :return: True if the key exists in metadata.
        """
        return key in self.metadata

    # --- Typed accessors for common calibration metadata ---

    @property
    def sensitivity_dbfs(self) -> float | None:
        """Microphone sensitivity in dBFS (set by calibrator)."""
        return self.metadata.get("sensitivity_dbfs")

    @property
    def reference_dbspl(self) -> float | None:
        """Reference SPL level in dBSPL (set by calibrator)."""
        return self.metadata.get("reference_dbspl")

    @property
    def calibration_applied(self) -> bool:
        """Whether full calibration (gain + FIR) was applied."""
        return self.metadata.get("calibration_applied", False)

    # --- Typed accessors for processing flags ---

    @property
    def gain_applied(self) -> bool:
        """Whether sensitivity gain correction was applied."""
        return self.metadata.get("gain_applied", False)

    @property
    def fir_applied(self) -> bool:
        """Whether FIR frequency correction was applied."""
        return self.metadata.get("fir_applied", False)

    @property
    def gain_linear(self) -> float | None:
        """The linear gain factor that was applied (if any)."""
        return self.metadata.get("gain_linear")

    @property
    def fir_num_taps(self) -> int | None:
        """Number of FIR filter taps used (if FIR was applied)."""
        return self.metadata.get("fir_num_taps")

    # --- Helper methods for calibration state ---

    def is_gain_calibrated(self) -> bool:
        """
        Check if audio has sensitivity (gain) calibration applied.

        When True, the audio levels have been corrected for microphone
        sensitivity. dBFS readings can be converted to dBSPL using only
        the reference SPL value.

        :return: True if gain calibration was applied with valid sensitivity data.
        """
        return self.gain_applied and self.sensitivity_dbfs is not None

    def is_frequency_calibrated(self) -> bool:
        """
        Check if audio has frequency response (FIR) calibration applied.

        When True, the audio has been corrected for microphone frequency
        response deviations. SPL measurements are accurate across the
        frequency spectrum.

        :return: True if FIR calibration was applied.
        """
        return self.fir_applied

    def is_fully_calibrated(self) -> bool:
        """
        Check if audio has both gain and frequency calibration.

        Fully calibrated audio provides the most accurate SPL measurements
        across all frequencies.

        :return: True if both gain and FIR calibration were applied.
        """
        return self.is_gain_calibrated() and self.is_frequency_calibrated()

    def can_calculate_dbspl(self) -> bool:
        """
        Check if dBSPL calculation is possible.

        dBSPL requires knowing the microphone sensitivity and reference SPL.
        These values are set by the calibrator when gain is applied.

        :return: True if sensitivity and reference values are available.
        """
        return self.sensitivity_dbfs is not None and self.reference_dbspl is not None

    def get_calibration_summary(self) -> dict[str, Any]:
        """
        Get a summary of the calibration state for logging/debugging.

        :return: Dict with calibration flags and values.
        """
        return {
            "gain_applied": self.gain_applied,
            "fir_applied": self.fir_applied,
            "fully_calibrated": self.is_fully_calibrated(),
            "sensitivity_dbfs": self.sensitivity_dbfs,
            "reference_dbspl": self.reference_dbspl,
            "gain_linear": self.gain_linear,
            "fir_num_taps": self.fir_num_taps,
        }
