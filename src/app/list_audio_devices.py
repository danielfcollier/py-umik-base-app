"""
Utility script to list all available audio input devices (microphones)
detected by the sounddevice library on the system.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from src import AudioDeviceSelector


def main():
    """
    The main function of the script.
    It directly calls the static method to display the audio devices.
    """
    AudioDeviceSelector.show_audio_devices()


if __name__ == "__main__":
    main()
