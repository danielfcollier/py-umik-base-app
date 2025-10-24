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
import os
import sys

from src import AudioDeviceCalibrator

# --- Configuration (Default Values) ---
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_NUM_TAPS = 1024


def get_sensitivity(calibration_file_path: str):
    """
    Extracts sensitivity values (dBFS and reference dBSPL) using the static
    method from the AudioDeviceCalibrator class.

    :param calibration_file_path: Path to the UMIK-1 calibration file.
    :raises SystemExit: If sensitivity extraction fails.
    """
    try:
        print("-" * 50)
        sensitivity_dbfs, reference_dbspl = AudioDeviceCalibrator.get_sensitivity_values(calibration_file_path)
        print("\n--- Sensitivity Values Extracted ---")
        print(f"Sensitivity: {sensitivity_dbfs:.3f} dBFS")
        print(f"Reference SPL: {reference_dbspl:.1f} dBSPL")
        print("-" * 50)

    except (FileNotFoundError, ValueError) as e:
        print(f"\n❌ ERROR: Could not extract sensitivity values: {e}")
        print("   Please ensure the file path is correct and the file contains")
        print("   a valid 'Sensitivity' or 'Sens Factor' line in the header.")
        print("-" * 50)
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
    print("-" * 50)
    print(f"Testing Calibrator initialization with file: {calibration_file_path}")
    print(f"Using sample rate: {device_sample_rate} Hz")
    print(f"Using filter taps: {num_taps}")
    print("-" * 50)

    try:
        AudioDeviceCalibrator(
            calibration_file_path=calibration_file_path,
            sample_rate=float(device_sample_rate),
            num_taps=num_taps,
            force_write=True,
        )
        print("\n✅ AudioDeviceCalibrator successfully initialized, filter designed!")
        print("-" * 50)

    except Exception as e:
        print(f"\n❌ ERROR: Failed to initialize AudioDeviceCalibrator: {e}")
        print("-" * 50)
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
        default=DEFAULT_SAMPLE_RATE,
        help=f"Sample rate (Hz) to use for filter design (default: {DEFAULT_SAMPLE_RATE}).",
    )

    parser.add_argument(
        "-t",
        "--num-taps",
        type=int,
        default=DEFAULT_NUM_TAPS,
        help=f"Number of FIR filter taps (coefficients) to design (default: {DEFAULT_NUM_TAPS}). "
        "Affects accuracy vs. CPU load. Common values: 256, 512, 1024.",
    )

    args = parser.parse_args()
    file_path = args.calibration_file
    sample_rate = args.sample_rate
    num_taps = args.num_taps

    if not os.path.isfile(file_path):
        print(f"❌ ERROR: The specified path is not a valid file: {file_path}")
        sys.exit(1)

    get_sensitivity(file_path)
    calibrate(sample_rate, file_path, num_taps)

    print("\n✅ All calibration tests completed successfully.")


if __name__ == "__main__":
    main()
