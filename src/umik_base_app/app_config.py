"""
Defines the configuration dataclass for the audio monitoring application.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from dataclasses import dataclass

from .calibration_config import CalibrationConfig
from .core.operational_mode import OperationalMode
from .hardwares.selector import HardwareSelector


@dataclass
class AppConfig:
    """
    Holds the validated and processed configuration settings for the audio
    application.

    All fields are set at construction time. Calibration is encapsulated
    in a separate CalibrationConfig object (None when disabled).
    """

    # Required fields (no defaults)
    sample_rate: float
    buffer_seconds: float
    run_mode: OperationalMode

    # Optional fields (with defaults)
    audio_device: HardwareSelector | None = None
    zmq_host: str | None = None
    zmq_port: int | None = None
    calibration: CalibrationConfig | None = None
