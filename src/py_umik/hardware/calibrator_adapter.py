"""
Defines an adapter class to integrate the HardwareCalibrator into the audio pipeline.

This module provides the HardwareCalibratorAdapter, which wraps the underlying
calibrator logic to satisfy the generic AudioTransformer protocol interface.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import numpy as np

from ..core.interfaces import AudioTransformer
from .calibrator import HardwareCalibrator


class HardwareCalibratorAdapter(AudioTransformer):
    def __init__(self, calibrator: HardwareCalibrator):
        self.calibrator = calibrator

    def process_audio(self, audio_chunk: np.ndarray) -> np.ndarray:
        return self.calibrator.apply(audio_chunk)
