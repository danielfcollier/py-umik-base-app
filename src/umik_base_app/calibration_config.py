"""
Encapsulates calibration-related configuration for calibrated microphones.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from dataclasses import dataclass

from .transformers.calibrator_transformer import CalibratorTransformer


@dataclass
class CalibrationConfig:
    """
    Encapsulates all calibration-related state.

    This dataclass groups the calibration file path, derived sensitivity
    values, filter configuration, and the transformer instance. If an
    application has a CalibrationConfig, calibration is enabled.
    """

    calibration_file_path: str
    sensitivity_dbfs: float  # Calculated from file (nominal + sens_factor)
    reference_dbspl: float   # Reference SPL (typically 94.0 dBSPL)
    num_taps: int
    transformer: CalibratorTransformer
