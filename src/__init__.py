"""
Initialization file for the audio_streams package.

This file marks the directory as a Python package and can be used to
define package-level objects or type hints, such as the callback definition.
"""

import logging
from typing import Callable
from datetime import datetime
import numpy as np

from src.library.audio_device.calibrator import AudioDeviceCalibrator
from src.library.audio_device.selector import AudioDeviceSelector


AudioProcessingCallback = Callable[[np.ndarray, datetime], None]


logging.basicConfig(level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")

__all__ = [
    "AudioDeviceCalibrator",
    "AudioDeviceSelector",
]
