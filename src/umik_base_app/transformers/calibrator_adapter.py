"""
Defines an adapter class to integrate the CalibratorTransformer into the audio pipeline.

This module provides the CalibratorAdapter, which wraps the underlying
calibrator logic to satisfy the generic AudioTransformer protocol interface.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import numpy as np

from .calibrator_transformer import CalibratorTransformer
from .transformers_protocol import AudioTransformer


class CalibratorAdapter(AudioTransformer):
    def __init__(self, calibrator: CalibratorTransformer):
        self.calibrator = calibrator

    def process_audio(self, audio_chunk: np.ndarray) -> np.ndarray:
        return self.calibrator.apply(audio_chunk)
