"""
Defines an adapter class to integrate the AudioDeviceCalibrator into the audio pipeline.

This module provides the AudioDeviceCalibratorAdapter, which wraps the underlying
calibrator logic to satisfy the generic AudioProcessor protocol interface.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import numpy as np

from src.library.audio_device.calibrator import AudioDeviceCalibrator
from src.library.interfaces import AudioProcessor


class AudioDeviceCalibratorAdapter(AudioProcessor):
    def __init__(self, calibrator: AudioDeviceCalibrator):
        self.calibrator = calibrator

    def process_audio(self, audio_chunk: np.ndarray) -> np.ndarray:
        return self.calibrator.apply(audio_chunk)
