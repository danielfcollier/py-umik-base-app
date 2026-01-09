"""
Script to test the initialization of the CalibratorTransformer (triggering
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

from umik_base_app.settings import get_settings
from umik_base_app.transformers.calibrator_transformer import CalibratorTransformer

settings = get_settings()
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


class CalibrationValidator:
    """
    Handles the validation logic for UMIK-1 calibration files.
    """

    def __init__(self, file_path: str, sample_rate: int, num_taps: int):
        self.file_path = file_path
        self.sample_rate = float(sample_rate)
        self.num_taps = num_taps

        if not os.path.isfile(self.file_path):
            raise FileNotFoundError(f"Calibration file not found: {self.file_path}")

    def show_sensitivity_info(self):
        """Extracts and prints sensitivity headers from the file."""
        try:
            sens_dbfs, ref_dbspl = CalibratorTransformer.get_sensitivity_values(
                self.file_path,
                settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS,
                settings.HARDWARE.REFERENCE_DBSPL,
            )
            logger.info("--- Sensitivity Data Extracted ---")
            logger.info(f"Sensitivity:   {sens_dbfs:.3f} dBFS")
            logger.info(f"Reference SPL: {ref_dbspl:.1f} dBSPL")
            logger.info("----------------------------------")
        except ValueError as e:
            logger.error(f"Error reading sensitivity data: {e}")
            sys.exit(1)

    def generate_and_cache_filter(self):
        """
        Instantiates CalibratorTransformer to trigger filter design and caching.
        """
        logger.info(f"Testing filter design for: {self.file_path}")
        logger.info(f"Target Sample Rate:    {self.sample_rate:.0f} Hz")
        logger.info(f"FIR Filter Taps:       {self.num_taps}")
        logger.info("----------------------------------")

        try:
            # Force write to ensure the cache is refreshed
            CalibratorTransformer(
                calibration_file_path=self.file_path,
                sample_rate=self.sample_rate,
                num_taps=self.num_taps,
                nominal_sensitivity_dbfs=settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS,
                reference_dbspl=settings.HARDWARE.REFERENCE_DBSPL,
                force_write=True,
            )
            logger.info("✅ SUCCESS: FIR filter designed and cached.")
        except Exception as e:
            logger.error(f"❌ FAILURE: Could not design filter. Reason: {e}")
            sys.exit(1)

    def run(self):
        """Execute the validation steps."""
        logger.info("Starting Calibration Validation...")
        self.show_sensitivity_info()
        self.generate_and_cache_filter()
        logger.info("Validation complete.")


def main():
    parser = argparse.ArgumentParser(description="Validate UMIK-1 calibration file and pre-calculate FIR filters.")

    parser.add_argument(
        "calibration_file",
        nargs="?",
        help="Path to the UMIK-1 calibration file (.txt). Defaults to CALIBRATION_FILE env var if set.",
    )

    parser.add_argument(
        "-r",
        "--sample-rate",
        type=int,
        default=settings.AUDIO.SAMPLE_RATE,
        help=f"Target sample rate in Hz (default: {settings.AUDIO.SAMPLE_RATE})",
    )

    parser.add_argument(
        "-t",
        "--num-taps",
        type=int,
        default=settings.AUDIO.NUM_TAPS,
        help=f"Number of FIR taps (default: {settings.AUDIO.NUM_TAPS})",
    )

    args = parser.parse_args()

    final_path = args.calibration_file or os.environ.get("CALIBRATION_FILE")

    if not final_path:
        logger.error("Error: No calibration file specified.")
        logger.error("Please provide a file path argument or set the CALIBRATION_FILE environment variable.")
        sys.exit(1)

    try:
        validator = CalibrationValidator(
            file_path=final_path,
            sample_rate=args.sample_rate,
            num_taps=args.num_taps,
        )
        validator.run()
    except Exception as e:
        logger.exception(f"Validation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
