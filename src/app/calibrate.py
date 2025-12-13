"""
Script to test the initialization of the AudioDeviceCalibrator (triggering
FIR filter design/caching) and extract sensitivity values from a UMIK-1
(or similar) calibration file provided as a command-line argument.

Allows specifying the sample rate and the number of FIR filter taps via CLI.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import logging
import os
import sys

from src import AudioDeviceCalibrator
from src.settings import settings

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


def get_sensitivity(calibration_file_path: str):
    """
    Extracts sensitivity values (dBFS and reference dBSPL) using the static
    method from the AudioDeviceCalibrator class.
    """
    try:
        sensitivity_dbfs, reference_dbspl = AudioDeviceCalibrator.get_sensitivity_values(calibration_file_path)
        logger.info("--- Sensitivity Values Extracted ---")
        logger.info(f"Sensitivity: {sensitivity_dbfs:.3f} dBFS")
        logger.info(f"Reference SPL: {reference_dbspl:.1f} dBSPL")
        logger.info("--------------------------------")

    except (FileNotFoundError, ValueError) as e:
        logger.error(f"Could not extract sensitivity values: {e}")
        logger.error("   Please ensure the file path is correct and the file contains")
        logger.error("   a valid 'Sensitivity' or 'Sens Factor' line in the header.")
        logger.error("-" * 50)
        sys.exit(1)


def calibrate(device_sample_rate: int, calibration_file_path: str, num_taps: int):
    """
    Initializes the AudioDeviceCalibrator class.

    This primarily tests the FIR filter design or cache loading mechanism within
    the AudioDeviceCalibrator's __init__ method, using the specified sample rate
    and number of filter taps.

    :param device_sample_rate: The sample rate (in Hz) to use for filter design (e.g., 48.000 Hz).
    :param calibration_file_path: Path to the UMIK-1 calibration file.
    :param num_taps: The number of coefficients (taps) for the FIR filter.
    :raises SystemExit: If initialization fails.
    """
    logger.info(f"Testing Calibrator initialization with file: {calibration_file_path}")
    logger.info(f"Using sample rate: {device_sample_rate} Hz")
    logger.info(f"Using filter taps: {num_taps}")
    logger.info("--------------------------------")

    try:
        AudioDeviceCalibrator(
            calibration_file_path=calibration_file_path,
            sample_rate=float(device_sample_rate),
            num_taps=num_taps,
            force_write=True,
        )
        logger.info("✅ AudioDeviceCalibrator successfully initialized (filter designed or loaded).")

    except Exception as e:
        logger.error(f"Failed to initialize AudioDeviceCalibrator: {e}", exc_info=True)  # Log traceback
        logger.error("-" * 50)
        sys.exit(1)


def main():
    """Parses command-line arguments and runs the calibration tests."""
    parser = argparse.ArgumentParser(
        description="Test AudioDeviceCalibrator initialization and extract sensitivity from a UMIK-1 file."
    )

    parser.add_argument("calibration_file", help="Path to the UMIK-1 calibration file (.txt).")

    parser.add_argument(
        "-r",
        "--sample-rate",
        type=int,
        default=settings.audio.sample_rate,
        help=f"Sample rate (Hz) to use for filter design (default: {settings.audio.sample_rate}).",
    )

    parser.add_argument(
        "-t",
        "--num-taps",
        type=int,
        default=settings.audio.num_taps,
        help=f"Number of FIR filter taps (coefficients) to design (default: {settings.audio.num_taps}). "
        "Affects accuracy vs. CPU load. Common values: 256, 512, 1024.",
    )

    args = parser.parse_args()
    file_path = args.calibration_file
    sample_rate = args.sample_rate
    num_taps = args.num_taps

    if not os.path.isfile(file_path):
        logger.error(f"The specified path is not a valid file: {file_path}")
        sys.exit(1)

    logger.info("Starting calibration test process...")
    get_sensitivity(file_path)
    calibrate(sample_rate, file_path, num_taps)

    logger.info("✅ All calibration tests completed successfully.")


if __name__ == "__main__":
    main()
