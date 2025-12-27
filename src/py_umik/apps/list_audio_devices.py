"""
Utility script to list all available audio input devices (microphones)
detected by the sounddevice library on the system.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging
import sys

from py_umik import HardwareSelector

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
logger = logging.getLogger(__name__)


def main():
    """
    The main function of the script.
    It directly calls the static method to display the audio devices.
    """
    HardwareSelector.show_audio_devices()


if __name__ == "__main__":
    main()
