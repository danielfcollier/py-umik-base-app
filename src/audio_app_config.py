"""
Defines classes and functions for parsing command-line arguments and setting up
the configuration for the audio monitoring application.

This module handles argument validation, device selection logic based on arguments,
and initialization of the calibration process if specified via command line.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import logging
import math
import sys

from src.library.audio_device.calibrator import AudioDeviceCalibrator
from src.library.audio_device.selector import AudioDeviceNotFound, AudioDeviceSelector

logger = logging.getLogger(__name__)

DEFAULT_BUFFER_SECONDS = 6
MINIMUM_BUFFER_SECONDS = 3
DEFAULT_SAMPLE_RATE = 48000
DEFAULT_NUM_TAPS = 1024
LUFS_AGGREGATION_SECONDS = 3  # Standard window for short-term LUFS calculation


class AudioAppConfig:
    """
    Holds the validated and processed configuration settings for the audio application.
    """

    def __init__(self, audio_device: AudioDeviceSelector, sample_rate: float, buffer_seconds: float):
        """
        Initializes the configuration object.

        :param audio_device: The selected AudioDeviceSelector instance.
        :param sample_rate: The final sample rate to be used (native or default).
        :param buffer_seconds: The validated and adjusted buffer duration in seconds.
        """
        self.audio_device: AudioDeviceSelector = audio_device
        self.sample_rate: float = sample_rate
        self.buffer_seconds: float = buffer_seconds
        self.audio_calibrator: AudioDeviceCalibrator | None = None
        self.sensitivity_dbfs: float | None = None
        self.reference_dbspl: float | None = None
        self.num_taps: int | None = None


class AudioAppArgs:
    """
    Handles parsing and validation of command-line arguments for the audio application.
    """

    @staticmethod
    def get_parser() -> argparse.ArgumentParser:
        """
        Creates and returns the ArgumentParser with standard arguments.
        Does NOT parse arguments immediately. Use this if you need to add custom
        arguments in your specific application (like --output-file).

        :return: An argparse.ArgumentParser object with standard flags configured.
        """
        parser = argparse.ArgumentParser(description="Run the Digital Decibel Meter / Audio Monitor application.")
        parser.add_argument(
            "--device-id",
            type=int,
            default=None,
            help="Target audio device ID (e.g., 7). Default: System default input device.",
        )
        parser.add_argument(
            "-b",
            "--buffer-seconds",
            type=float,
            default=DEFAULT_BUFFER_SECONDS,
            help=(
                f"Duration of audio buffers in seconds. "
                f"Minimum: {MINIMUM_BUFFER_SECONDS}s. Will be rounded up to a multiple "
                f"of LUFS window ({LUFS_AGGREGATION_SECONDS}s). Default: {DEFAULT_BUFFER_SECONDS}s."
            ),
        )
        parser.add_argument(
            "-r",
            "--sample-rate",
            type=float,
            default=DEFAULT_SAMPLE_RATE,
            help=(
                f"Target sample rate (Hz) for default device. Default: {DEFAULT_SAMPLE_RATE} Hz. "
                "This is IGNORED if --calibration-file is used, as the device's native rate takes precedence."
            ),
        )
        parser.add_argument(
            "-c",
            "--calibration-file",
            type=str,
            default=None,
            help=(
                "Path to the microphone calibration file (.txt, e.g., from UMIK-1). "
                "If provided, the device's native sample rate will be used, overriding --sample-rate. "
                "Required if specifying a non-default --device-id."
            ),
        )
        parser.add_argument(
            "-t",
            "--num-taps",
            type=int,
            default=DEFAULT_NUM_TAPS,
            help=(
                "Number of FIR filter taps for calibration filter design (only used with --calibration-file). "
                f"Affects accuracy vs CPU load. Default: {DEFAULT_NUM_TAPS}."
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
        parser = AudioAppArgs.get_parser()
        args = parser.parse_args()
        return args

    @staticmethod
    def validate_args(args: argparse.Namespace) -> AudioAppConfig:
        """
        Validates the parsed command-line arguments and creates the final AudioAppConfig object.

        Performs checks and adjustments:
        - Ensures buffer_seconds meets the minimum and is a multiple of the LUFS window.
        - Selects the audio device (default or specified ID).
        - Determines the final sample rate (uses native rate if calibrating).
        - Initializes the AudioDeviceCalibrator and extracts sensitivity if a calibration file is provided.
        - Raises exceptions for invalid configurations (e.g., missing calibration file for non-default device).

        :param args: The argparse.Namespace object containing parsed arguments from get_args().
        :return: A populated and validated AudioAppConfig object.
        :raises ValueError: If configuration is invalid (e.g., missing calibration file).
        :raises AudioDeviceNotFound: If the specified device ID cannot be found.
        :raises SystemExit: If calibration file parsing or filter design fails.
        """
        logger.info("Validating command-line arguments...")

        buffer_seconds = float(args.buffer_seconds)
        if buffer_seconds < MINIMUM_BUFFER_SECONDS:
            logger.warning(
                f"Requested buffer size ({buffer_seconds:.2f}s) is below minimum ({MINIMUM_BUFFER_SECONDS:.1f}s). "
                f"Adjusting buffer size to {MINIMUM_BUFFER_SECONDS:.1f}s."
            )
            buffer_seconds = MINIMUM_BUFFER_SECONDS
        elif buffer_seconds % LUFS_AGGREGATION_SECONDS != 0:
            new_buffer = math.ceil(buffer_seconds / LUFS_AGGREGATION_SECONDS) * LUFS_AGGREGATION_SECONDS
            logger.warning(
                f"Adjusting buffer size from {buffer_seconds:.2f}s to {new_buffer:.1f}s to be an even multiple of "
                f"the LUFS window ({LUFS_AGGREGATION_SECONDS:.1f}s)."
            )
            buffer_seconds = new_buffer

        try:
            selected_audio_device = AudioDeviceSelector(target_id=args.device_id)
            logger.info(f"Selected audio device: ID={selected_audio_device.id}, Name='{selected_audio_device.name}'")
        except AudioDeviceNotFound as e:
            logger.error(f"Failed to select audio device: {e}")
            sys.exit(1)

        final_sample_rate = float(args.sample_rate)

        config = AudioAppConfig(
            audio_device=selected_audio_device,
            sample_rate=final_sample_rate,
            buffer_seconds=buffer_seconds,
        )

        if not config.audio_device.is_default:
            if not args.calibration_file:
                logger.error(
                    "A calibration file (--calibration-file) is required when specifying a non-default device ID."
                )
                raise ValueError("Calibration file required for specified device.")

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
                config.sample_rate = final_sample_rate  # Fallback

            sensitivity_dbfs, reference_dbspl = AudioDeviceCalibrator.get_sensitivity_values(args.calibration_file)
            config.audio_calibrator = AudioDeviceCalibrator(
                calibration_file_path=args.calibration_file,
                sample_rate=config.sample_rate,
                num_taps=args.num_taps,
            )

            config.sensitivity_dbfs = sensitivity_dbfs
            config.reference_dbspl = reference_dbspl
            config.num_taps = args.num_taps
            logger.info("Calibration enabled and initialized.")

        else:
            logger.info("No calibration file provided and default device selected. Calibration disabled.")
            logger.info(f"Using specified/default sample rate: {config.sample_rate:.0f} Hz.")

        logger.info(
            f"Final Configuration: SR={config.sample_rate:.0f} Hz, Buffer={config.buffer_seconds:.1f}s,"
            f" Calibrated={config.audio_calibrator is not None}"
        )
        return config
