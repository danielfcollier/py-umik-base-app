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

from .app_config import AppConfig
from .hardwares.selector import HardwareNotFound, HardwareSelector
from .settings import get_settings
from .transformers.calibrator_transformer import CalibratorTransformer

settings = get_settings()

logger = logging.getLogger(__name__)


class AppArgs:
    """
    Handles parsing and validation of command-line arguments for the audio application.
    """

    @staticmethod
    def get_parser() -> argparse.ArgumentParser:
        """
        Creates and returns the ArgumentParser with standard arguments.
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

        group = parser.add_argument_group("Topology / ZMQ")
        group.add_argument(
            "--producer", action="store_true", help="Run in Producer (Capture) mode only, sending data via ZMQ."
        )
        group.add_argument(
            "--consumer", action="store_true", help="Run in Consumer (Processing) mode only, receiving data via ZMQ."
        )
        group.add_argument(
            "--zmq-host",
            type=str,
            default=settings.ZMQ.HOST,
            help=f"ZMQ Host (for consumer to connect). Default: {settings.ZMQ.HOST}",
        )
        group.add_argument(
            "--zmq-port", type=int, default=settings.ZMQ.PORT, help=f"ZMQ Port. Default: {settings.ZMQ.PORT}"
        )

        return parser

    @staticmethod
    def get_args() -> argparse.Namespace:
        """
        Defines and parses command-line arguments using argparse.
        """
        parser = AppArgs.get_parser()
        args = parser.parse_args()
        return args

    @staticmethod
    def validate_args(args: argparse.Namespace) -> AppConfig:
        """
        Validates the parsed command-line arguments and creates the final AppConfig object.
        """
        logger.info("Validating command-line arguments...")

        # --- 1. Topology / Run Mode ---
        if args.producer and args.consumer:
            logger.error("Cannot be both Producer and Consumer separately. Do not set flags for Monolithic mode.")
            sys.exit(1)

        run_mode = "monolithic"
        if args.producer:
            run_mode = "producer"
        elif args.consumer:
            run_mode = "consumer"

        # --- 2. Resolve Calibration File (Arg > Env) ---
        if args.calibration_file is None and not args.default:
            env_cal_file = os.environ.get("CALIBRATION_FILE")
            if env_cal_file:
                logger.info(f"Found CALIBRATION_FILE env var: {env_cal_file}")
                args.calibration_file = env_cal_file
        elif args.default and args.calibration_file is None:
            logger.info("Flag --default set. Ignoring CALIBRATION_FILE environment variable.")

        # --- 3. Hardware Selection (Skip if Consumer) ---
        selected_audio_device = None

        if run_mode != "consumer":
            # Auto-Detect Target Device (e.g. UMIK-1) if needed
            if args.calibration_file and args.device_id is None and not args.default:
                target_name = settings.HARDWARE.TARGET_DEVICE_NAME
                logger.info(f"Calibration file active. Attempting to auto-detect '{target_name}'...")
                try:
                    # No argument needed, defaults to settings target
                    target_id = HardwareSelector.find_device_by_name()
                    if target_id is not None:
                        logger.info(f"✨ Auto-detected {target_name} at Device ID {target_id}")
                        args.device_id = target_id
                    else:
                        logger.warning(
                            f"⚠️ Could not find a device named '{target_name}'. Will attempt to use system default."
                        )
                except Exception as e:
                    logger.warning(f"Hardware detection failed during auto-discovery: {e}")

            # Select Device
            try:
                target_id = None if args.default else args.device_id
                selected_audio_device = HardwareSelector(target_id=target_id)
                logger.info(
                    f"Selected audio device: ID={selected_audio_device.id}, Name='{selected_audio_device.name}'"
                )
            except HardwareNotFound as e:
                logger.error(f"Failed to select audio device: {e}")
                sys.exit(1)
        else:
            logger.info("Running as Consumer: Skipping local hardware selection.")

        # --- 4. Buffer Validation ---
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

        final_sample_rate = float(args.sample_rate)

        config = AppConfig(
            audio_device=selected_audio_device,
            sample_rate=final_sample_rate,
            buffer_seconds=buffer_seconds,
            run_mode=run_mode,
            zmq_host=args.zmq_host,
            zmq_port=args.zmq_port,
        )

        # --- 5. Calibration Setup ---
        if args.calibration_file:
            logger.info(f"Calibration file provided: {args.calibration_file}. Enabling calibration.")

            # Attempt to use native rate if device is available (Producer/Monolithic)
            if config.audio_device:
                try:
                    native_rate = float(config.audio_device.native_rate)
                    if native_rate > 0:
                        config.sample_rate = native_rate
                        logger.info(f"Using device native sample rate for calibration: {config.sample_rate:.0f} Hz.")
                    else:
                        raise ValueError(f"Invalid native rate: {native_rate}")

                except (AttributeError, ValueError, TypeError) as e:
                    logger.error(f"Could not use native rate from device. Error: {e}")
                    logger.warning(f"Falling back to requested sample rate: {final_sample_rate:.0f} Hz.")
                    config.sample_rate = final_sample_rate
            else:
                # Consumer mode with calibration (e.g., calibrating raw stream)
                logger.info(
                    f"Consumer mode: Using requested sample rate for calibration context: {final_sample_rate:.0f} Hz."
                )
                config.sample_rate = final_sample_rate

            sensitivity_dbfs, reference_dbspl = CalibratorTransformer.get_sensitivity_values(
                args.calibration_file,
                settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS,
                settings.HARDWARE.REFERENCE_DBSPL,
            )

            config.audio_calibrator = CalibratorTransformer(
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
            f"Final Configuration: Mode={run_mode}, SR={config.sample_rate:.0f}Hz, "
            f"Buffer={config.buffer_seconds:.1f}s, Calibrated={config.audio_calibrator is not None}"
        )
        return config
