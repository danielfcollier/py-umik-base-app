"""
Defines the configuration dataclass for the audio monitoring application.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from dataclasses import dataclass

from .core.operational_mode import OperationalMode
from .hardwares.selector import HardwareSelector
from .transformers.calibrator_transformer import CalibratorTransformer


@dataclass
class AppConfig:
    """
    Holds the validated and processed configuration settings for the audio
    application.

    All fields are set at construction time. Calibration-related fields
    default to None when calibration is not enabled.
    """

    # Required fields (no defaults)
    sample_rate: float
    buffer_seconds: float
    run_mode: OperationalMode

    # Optional fields (with defaults)
    audio_device: HardwareSelector | None = None
    zmq_host: str | None = None
    zmq_port: int | None = None
    audio_calibrator: CalibratorTransformer | None = None
    num_taps: int | None = None
