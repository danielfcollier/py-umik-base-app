"""
A module for discovering and selecting audio input devices (microphones)
using the sounddevice library. It provides a robust class to automatically
select the system's default microphone or find a specific one by name.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import sounddevice as sd


class AudioDeviceNotFound(Exception):
    """Custom exception raised when a specified audio device cannot be found."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class AudioDeviceSelector:
    """A class to handle the selection and validation of an audio input device."""

    def __init__(self, target: int | None):
        """
        Initializes the selector and finds the specified audio device.

        If a target ID is provided, it gets a matching device.
        If the target is None, it selects the system's default input device.

        :param target: The name (or partial name) of the microphone to find.
        """
        self.data: dict = self._get_audio_device(target)
        self.id: int = self.data["index"]
        self.name: str = self.data["name"]
        self.is_default: bool = self.name == "default"

        AudioDeviceSelector.show_audio_devices(self.id)

    def _get_audio_device(self, target: int | None = None) -> dict:
        """
        Queries the system for available devices and returns the desired one.

        :param target: The ID of the device to search for.
        :return: A dictionary containing the device's information.
        :raises AudioDeviceNotFound: If the target device is not found.
        """

        try:
            audio_devices: list[dict] = list(sd.query_devices())
            default_audio_device_id = sd.default.device[0]

            if not target:
                print(f"No target specified. Selecting default input device (ID: {default_audio_device_id})...")
                return next(filter(lambda device: device["index"] == default_audio_device_id, audio_devices))

            print(f"Searching for an input device index '{target}'...")
            target_audio_device: dict | None = next(
                filter(lambda device: target == device["index"] and device["max_input_channels"] > 0, audio_devices),
                None,
            )

            if target_audio_device is None:
                raise AudioDeviceNotFound(message=f"Device not found in device list {audio_devices}")

            print(f"✅ Found device: {target_audio_device['name']}")
            return target_audio_device

        except AudioDeviceNotFound as e:
            print(f"❌ {e.message}")
            AudioDeviceSelector.show_audio_devices()
            raise
        except Exception as e:
            print(f"❌ An unexpected error occurred while getting audio devices: {e}")
            raise

    @staticmethod
    def show_audio_devices(selected_id: int | None = None):
        """
        Prints a formatted list of all available input devices.
        This is a utility method useful for debugging.

        :param selected_id: The ID of the device to highlight with a '>' marker.
        """
        print("--- Listing all available input audio devices ---")
        try:
            audio_devices: list[dict] = list(sd.query_devices())
            input_devices_found = False
            for audio_device in audio_devices:
                if audio_device["max_input_channels"] > 0:
                    input_devices_found = True
                    index: int = audio_device["index"]
                    name: str = audio_device["name"]
                    # Add a marker to indicate which device is currently selected.
                    marker: str = ">" if index == selected_id else " "

                    print(f"{marker} ID {index} - {name}")

            if not input_devices_found:
                print("No input devices were found on this system.")
        except Exception as e:
            print(f"❌ Could not query audio devices: {e}")
