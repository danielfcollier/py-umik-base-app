"""
Defines classes and functions for parsing command-line arguments and setting up
the configuration for the audio monitoring application.

This module handles argument validation, device selection logic based on arguments,
and initialization of the calibration process if specified via command line
or environment variable.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import logging
import math
import os
import sys

from ..hardware.calibrator import HardwareCalibrator
from ..hardware.selector import HardwareNotFound, HardwareSelector
from ..settings import get_settings

settings = get_settings()

logger = logging.getLogger(__name__)


class AppConfig:
    """
    Holds the validated and processed configuration settings for the audio application.
    """

    def __init__(self, audio_device: HardwareSelector, sample_rate: float, buffer_seconds: float):
        """
        Initializes the configuration object.

        :param audio_device: The selected HardwareSelector instance.
        :param sample_rate: The final sample rate to be used (native or default).
        :param buffer_seconds: The validated and adjusted buffer duration in seconds.
        """
        self.audio_device: HardwareSelector = audio_device
        self.sample_rate: float = sample_rate
        self.buffer_seconds: float = buffer_seconds
        self.audio_calibrator: HardwareCalibrator | None = None
        self.sensitivity_dbfs: float | None = None
        self.reference_dbspl: float | None = None
        self.num_taps: int | None = None


class AppArgs:
    """
    Handles parsing and validation of command-line arguments for the audio application.
    """

    @staticmethod
    def get_parser() -> argparse.ArgumentParser:
        """
        Creates and returns the ArgumentParser with standard arguments.
        Does NOT parse arguments immediately. Use this if you need to add custom
        arguments in your specific application (like --output-dir).

        :return: An argparse.ArgumentParser object with standard flags configured.
        """
        parser = argparse.ArgumentParser(description="Run the Digital Real Time Meter / Audio Monitor application.")
        parser.add_argument(
            "--device-id",
            type=int,
            default=None,
            help="Target audio device ID (e.g., 7). Default: System default input device.",
        )
        parser.add_argument(
            "--default",
            action="store_true",
            help="Force use of default microphone, ignoring CALIBRATION_FILE environment variable.",
        )
        parser.add_argument(
            "-b",
            "--buffer-seconds",
            type=float,
            default=settings.AUDIO.BUFFER_SECONDS,
            help=(
                f"Duration of audio buffers in seconds. "
                f"Minimum: {settings.AUDIO.MIN_BUFFER_SECONDS}s. Will be rounded up to a multiple "
                f"of LUFS window ({settings.AUDIO.LUFS_WINDOW_SECONDS}s). "
                f"Default: {settings.AUDIO.BUFFER_SECONDS}s."
            ),
        )
        parser.add_argument(
            "-r",
            "--sample-rate",
            type=float,
            default=settings.AUDIO.SAMPLE_RATE,
            help=(
                f"Target sample rate (Hz) for default device. Default: {settings.AUDIO.SAMPLE_RATE} Hz. "
                "This is IGNORED if --calibration-file is used (arg or env var), as the device's native rate takes "
                "precedence."
            ),
        )
        parser.add_argument(
            "-c",
            "--calibration-file",
            type=str,
            default=None,
            help=(
                "Path to the microphone calibration file (.txt, e.g., from UMIK-1). "
                "Can also be set via CALIBRATION_FILE environment variable. "
                "Argument overrides env var. "
                "Presence triggers auto-detection of 'UMIK-1' device if --device-id is not set."
            ),
        )
        parser.add_argument(
            "-t",
            "--num-taps",
            type=int,
            default=settings.AUDIO.NUM_TAPS,
            help=(
                "Number of FIR filter taps for calibration filter design (only used with --calibration-file). "
                f"Affects accuracy vs CPU load. Default: {settings.AUDIO.NUM_TAPS}."
            ),
        )
        return parser

    @staticmethod
    def get_args() -> argparse.Namespace:
        """
        Defines and parses command-line arguments using argparse.
        This remains for backward compatibility with apps that don't need custom args.

        :return: An argparse.Namespace object containing the parsed arguments.
        """
        parser = AppArgs.get_parser()
        args = parser.parse_args()
        return args

    @staticmethod
    def validate_args(args: argparse.Namespace) -> AppConfig:
        """
        Validates the parsed command-line arguments and creates the final AppConfig object.
        Performs checks and adjustments:
        - Resolves calibration file from Arg or Env Var.
        - Ensures buffer_seconds meets the minimum and is a multiple of the LUFS window.
        - Auto-detects UMIK-1 if calibration file is present but device ID is missing.
        - Selects the audio device (default or specified ID).
        - Determines the final sample rate (uses native rate if calibrating).
        - Initializes the HardwareCalibrator and extracts sensitivity if a calibration file is provided.
        - Catches device selection errors (HardwareNotFound) and exits the application.

        :param args: The argparse.Namespace object containing parsed arguments from get_args().
        :return: A populated and validated AppConfig object.
        :raises ValueError: If configuration is invalid.
        :raises SystemExit: If the specified device ID cannot be found.
        """
        logger.info("Validating command-line arguments...")

        # --- 1. Resolve Calibration File (Arg > Env) ---
        if args.calibration_file is None and not args.default:
            env_cal_file = os.environ.get("CALIBRATION_FILE")
            if env_cal_file:
                logger.info(f"Found CALIBRATION_FILE env var: {env_cal_file}")
                args.calibration_file = env_cal_file
        elif args.default and args.calibration_file is None:
            logger.info("Flag --default set. Ignoring CALIBRATION_FILE environment variable.")

        # --- 2. Auto-Detect UMIK-1 if needed ---
        if args.calibration_file and args.device_id is None and not args.default:
            logger.info("Calibration file active. Attempting to auto-detect 'UMIK-1'...")
            umik_id = HardwareSelector.find_device_by_name("UMIK-1")
            if umik_id is not None:
                logger.info(f"✨ Auto-detected UMIK-1 at Device ID {umik_id}")
                args.device_id = umik_id
            else:
                logger.warning("⚠️ Could not find a device named 'UMIK-1'. Will attempt to use system default.")

        # --- 3. Buffer Validation ---
        buffer_seconds = float(args.buffer_seconds)
        min_buf = settings.AUDIO.MIN_BUFFER_SECONDS
        lufs_window = settings.AUDIO.LUFS_WINDOW_SECONDS

        if buffer_seconds < min_buf:
            logger.warning(
                f"Requested buffer size ({buffer_seconds:.2f}s) is below minimum ({min_buf:.1f}s). "
                f"Adjusting buffer size to {min_buf:.1f}s."
            )
            buffer_seconds = min_buf
        elif buffer_seconds % lufs_window != 0:
            new_buffer = math.ceil(buffer_seconds / lufs_window) * lufs_window
            logger.warning(
                f"Adjusting buffer size from {buffer_seconds:.2f}s to {new_buffer:.1f}s to be an even multiple of "
                f"the LUFS window ({lufs_window:.1f}s)."
            )
            buffer_seconds = new_buffer

        # --- 4. Hardware Selection ---
        try:
            target_id = None if args.default else args.device_id
            selected_audio_device = HardwareSelector(target_id=target_id)
            logger.info(f"Selected audio device: ID={selected_audio_device.id}, Name='{selected_audio_device.name}'")
        except HardwareNotFound as e:
            logger.error(f"Failed to select audio device: {e}")
            sys.exit(1)

        final_sample_rate = float(args.sample_rate)

        config = AppConfig(
            audio_device=selected_audio_device,
            sample_rate=final_sample_rate,
            buffer_seconds=buffer_seconds,
        )

        # --- 5. Calibration Setup ---
        if args.calibration_file:
            logger.info(f"Calibration file provided: {args.calibration_file}. Enabling calibration.")

            try:
                native_rate = float(config.audio_device.native_rate)
                if native_rate <= 0:
                    raise ValueError(
                        f"Invalid native sample rate reported by device: {config.audio_device.native_rate}"
                    )
                config.sample_rate = native_rate
                logger.info(f"Using device native sample rate for calibration: {config.sample_rate:.0f} Hz.")

            except (AttributeError, ValueError, TypeError) as e:
                logger.error(
                    f"Could not determine or use native sample rate from selected device ({config.audio_device.name})."
                    f" Error: {e}"
                )
                logger.warning(
                    f"Falling back to specified/default sample rate: {final_sample_rate:.0f} Hz."
                    f" Calibration accuracy may be affected."
                )
                config.sample_rate = final_sample_rate

            sensitivity_dbfs, reference_dbspl = HardwareCalibrator.get_sensitivity_values(args.calibration_file)
            config.audio_calibrator = HardwareCalibrator(
                calibration_file_path=args.calibration_file,
                sample_rate=config.sample_rate,
                num_taps=args.num_taps,
            )

            config.sensitivity_dbfs = sensitivity_dbfs
            config.reference_dbspl = reference_dbspl
            config.num_taps = args.num_taps
            logger.info("Calibration enabled and initialized.")

        else:
            logger.info("No calibration file provided (Arg or Env). Calibration disabled.")
            logger.info(f"Using specified/default sample rate: {config.sample_rate:.0f} Hz.")

        logger.info(
            f"Final Configuration: SR={config.sample_rate:.0f} Hz, Buffer={config.buffer_seconds:.1f}s,"
            f" Calibrated={config.audio_calibrator is not None}"
        )
        return config
