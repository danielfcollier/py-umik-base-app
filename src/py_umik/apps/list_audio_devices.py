"""
Utility script to list all available audio input devices (microphones)
detected by the sounddevice library on the system.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import argparse
import logging
import sys

from py_umik import HardwareSelector

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


def main():
    """
    The main function of the script.
    It parses command line arguments to either list all devices or find a specific UMIK-1 ID.
    """
    parser = argparse.ArgumentParser(description="List available audio input devices.")
    parser.add_argument(
        "--only",
        action="store_true",
        help="If set, searches specifically for a 'UMIK-1' device and prints ONLY its ID.",
    )

    args = parser.parse_args()

    if args.only:
        device_id = HardwareSelector.find_device_by_name("UMIK-1")
        if device_id is not None:
            print(device_id)
        else:
            sys.exit(1)
    else:
        HardwareSelector.show_audio_devices()


if __name__ == "__main__":
    main()
