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
from pathlib import Path

from .app_config import AppConfig
from .calibration_config import CalibrationConfig
from .core.operational_mode import OperationalMode
from .hardwares.device_profiles import find_profile_by_name
from .hardwares.selector import HardwareNotFound, HardwareSelector
from .settings import get_settings
from .transformers.calibrator_transformer import CalibratorTransformer

settings = get_settings()

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path.home() / ".config" / "audio-tools"
_SYSTEM_CONFIG_DIR = Path("/etc/audio-tools")


def _resolve_calibration_file() -> str | None:
    search_dirs = [d for d in (_CONFIG_DIR, _SYSTEM_CONFIG_DIR) if d.is_dir()]
    if not search_dirs:
        return None
    cal_files: list[Path] = []
    for d in search_dirs:
        cal_files.extend(sorted(d.rglob("*.txt")))
    if not cal_files:
        return None
    if len(cal_files) == 1:
        logger.info(f"Auto-discovered calibration file: {cal_files[0]}")
        return str(cal_files[0])
    print("\nMultiple calibration files found:", file=sys.stderr)
    for i, path in enumerate(cal_files, 1):
        for base, label in ((_CONFIG_DIR, "~/.config/audio-tools/"), (_SYSTEM_CONFIG_DIR, "/etc/audio-tools/")):
            try:
                print(f"  [{i}] {label}{path.relative_to(base)}", file=sys.stderr)
                break
            except ValueError:
                continue
        else:
            print(f"  [{i}] {path}", file=sys.stderr)
    while True:
        try:
            choice = input(f"Select calibration file [1-{len(cal_files)}]: ").strip()
            idx = int(choice) - 1
            if 0 <= idx < len(cal_files):
                selected = str(cal_files[idx])
                logger.info(f"Selected calibration file: {selected}")
                return selected
        except (ValueError, EOFError):
            pass
        print(f"Invalid selection. Enter a number between 1 and {len(cal_files)}.", file=sys.stderr)


def _warn_calibrated_mic_without_file(mic_name: str) -> None:
    print(
        f"\n  WARNING: '{mic_name}' is a calibrated microphone but no calibration file was found.\n"
        f"  Measurements will show dBFS only — dBSPL requires a calibration file.\n"
        f"\n"
        f"  Supply one via:\n"
        f"    --calibration-file /path/to/file.txt\n"
        f"    CALIBRATION_FILE=...  (environment variable)\n"
        f"    cp file.txt ~/.config/audio-tools/   (auto-discovery, per-user)\n"
        f"    cp file.txt /etc/audio-tools/         (auto-discovery, system-wide)\n"
        f"\n"
        f"  Sample calibration files shipped with this package:\n"
        f"    /usr/share/audio-tools/calibration/\n"
        f"\n"
        f"  Use --default to bypass this check and run uncalibrated.\n",
        file=sys.stderr,
    )
    if not sys.stdin.isatty():
        logger.error("Non-interactive mode: refusing to run calibrated mic without calibration file.")
        sys.exit(1)
    try:
        answer = input("  Continue without calibration? [y/N]: ").strip().lower()
    except EOFError:
        sys.exit(1)
    if answer not in ("y", "yes"):
        sys.exit(0)
    print("", file=sys.stderr)


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
                "If omitted, falls back to CALIBRATION_FILE env var, then auto-discovers "
                "from ~/.config/audio-tools/ (prompts a selector if multiple files are found). "
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

        parser.add_argument(
            "--log-file",
            type=str,
            default=argparse.SUPPRESS,
            metavar="FILE",
            help="Write logs to FILE instead of stderr. Use --log-append to append rather than overwrite.",
        )
        parser.add_argument(
            "--log-append",
            action="store_true",
            default=argparse.SUPPRESS,
            help="Append to --log-file instead of overwriting it.",
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

        run_mode = OperationalMode.MONOLITHIC
        if args.producer:
            run_mode = OperationalMode.PRODUCER
        elif args.consumer:
            run_mode = OperationalMode.CONSUMER

        # --- 2. Resolve Calibration File (Arg > Env > ~/.config/audio-tools/) ---
        if args.calibration_file is None and not args.default:
            env_cal_file = os.environ.get("CALIBRATION_FILE")
            if env_cal_file:
                logger.info(f"Found CALIBRATION_FILE env var: {env_cal_file}")
                args.calibration_file = env_cal_file
            else:
                args.calibration_file = _resolve_calibration_file()
        elif args.default and args.calibration_file is None:
            logger.info("Flag --default set. Ignoring CALIBRATION_FILE environment variable.")

        # --- 3. Hardware Selection (Skip if Consumer) ---
        selected_audio_device = None

        if run_mode != OperationalMode.CONSUMER:
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

        # --- 5. Calibration Setup & Final Sample Rate ---
        calibration = None
        final_sample_rate = float(args.sample_rate)

        if args.calibration_file:
            logger.info(f"Calibration file provided: {args.calibration_file}. Enabling calibration.")

            # Determine sample rate for calibration
            if selected_audio_device:
                try:
                    native_rate = float(selected_audio_device.native_rate)
                    if native_rate > 0:
                        final_sample_rate = native_rate
                        logger.info(f"Using device native sample rate for calibration: {final_sample_rate:.0f} Hz.")
                    else:
                        raise ValueError(f"Invalid native rate: {native_rate}")
                except (AttributeError, ValueError, TypeError) as e:
                    logger.error(f"Could not use native rate from device. Error: {e}")
                    logger.warning(f"Falling back to requested sample rate: {final_sample_rate:.0f} Hz.")
            else:
                logger.info(f"Consumer mode: Using requested sample rate: {final_sample_rate:.0f} Hz.")

            transformer = CalibratorTransformer(
                calibration_file_path=args.calibration_file,
                sample_rate=final_sample_rate,
                num_taps=args.num_taps,
                nominal_sensitivity_dbfs=settings.HARDWARE.NOMINAL_SENSITIVITY_DBFS,
                reference_dbspl=settings.HARDWARE.REFERENCE_DBSPL,
            )

            calibration = CalibrationConfig(
                calibration_file_path=args.calibration_file,
                sensitivity_dbfs=transformer.sensitivity_dbfs,
                reference_dbspl=transformer.reference_dbspl,
                num_taps=args.num_taps,
                transformer=transformer,
            )
            logger.info("Calibration enabled and initialized.")
        else:
            if not args.default and selected_audio_device is not None:
                profile = find_profile_by_name(selected_audio_device.name)
                if profile is not None:
                    _warn_calibrated_mic_without_file(profile.name)
            logger.info("No calibration file provided. Calibration disabled.")
            logger.info(f"Using sample rate: {final_sample_rate:.0f} Hz.")

        # --- 6. Create AppConfig in a single call ---
        config = AppConfig(
            sample_rate=final_sample_rate,
            buffer_seconds=buffer_seconds,
            run_mode=run_mode,
            audio_device=selected_audio_device,
            zmq_host=args.zmq_host,
            zmq_port=args.zmq_port,
            calibration=calibration,
        )

        logger.info(
            f"Final Configuration: Mode={run_mode.value}, "
            f"SR={config.sample_rate:.0f}Hz, "
            f"Buffer={config.buffer_seconds:.1f}s, "
            f"Calibrated={config.calibration is not None}"
        )
        return config
