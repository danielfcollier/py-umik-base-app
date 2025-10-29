"""
A module for discovering and selecting audio input devices (microphones)
using the sounddevice library. It provides a robust class to automatically
select the system's default microphone or find a specific one by name.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import logging

import sounddevice as sd

logger = logging.getLogger(__name__)


class AudioDeviceNotFound(Exception):
    """Custom exception raised when a specified audio device cannot be found."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class AudioDeviceSelector:
    """A class to handle the selection and validation of an audio input device."""

    def __init__(self, target_id: int | None):
        """
        Initializes the selector and finds the specified audio device.

        If a target_id is provided, it gets a matching device.
        If the target_id is None, it selects the system's default input device.

        :param target_id: The ID of the microphone to find.
        """
        self.data: dict = self._get_audio_device(target_id)
        self.id: int = self.data["index"]
        self.name: str = self.data["name"]
        self.native_rate: str = self.data["default_samplerate"]
        self.is_default: bool = self.name == "default"

        AudioDeviceSelector.show_audio_devices(self.id)

    def _get_audio_device(self, target_id: int | None = None) -> dict:
        """
        Queries the system for available devices and returns the desired one.

        :param target_id: The ID of the device to search for.
        :return: A dictionary containing the device's information.
        :raises AudioDeviceNotFound: If the target_id device is not found.
        """

        try:
            audio_devices: list[dict] = list(sd.query_devices())
            default_audio_device_id = sd.default.device[0]

            if not target_id:
                logger.warning(
                    f"No target specified. Selecting default input device (ID: {default_audio_device_id})..."
                )
                return next(filter(lambda device: device["index"] == default_audio_device_id, audio_devices))

            logger.debug(f"Searching for an input device index '{target_id}'...")
            target_audio_device: dict | None = next(
                filter(lambda device: target_id == device["index"] and device["max_input_channels"] > 0, audio_devices),
                None,
            )

            if target_audio_device is None:
                logger.warning("Failed to select audio device. Exiting.", exc_info=True)
                raise AudioDeviceNotFound(message=f"Device not found in device list {audio_devices}")

            target_name = target_audio_device["name"]
            logger.info(f"✅ Selected audio device: ID={target_id}, Name={target_name}")

            return target_audio_device

        except AudioDeviceNotFound as e:
            logger.critical(f"❌ {e.message}")
            AudioDeviceSelector.show_audio_devices()
            exit(1)
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred while getting audio devices: {e}")
            raise

    @staticmethod
    def show_audio_devices(selected_id: int | None = None):
        """
        Prints a formatted list of all available input devices.
        This is a utility method useful for debugging.

        :param selected_id: The ID of the device to highlight with a '>' marker.
        """
        logger.info("--- Listing all available input audio devices ---")
        try:
            audio_devices: list[dict] = list(sd.query_devices())
            input_devices_found = False
            for audio_device in audio_devices:
                if audio_device["max_input_channels"] > 0:
                    input_devices_found = True
                    index: int = audio_device["index"]
                    name: str = audio_device["name"]
                    native_rate: str = audio_device["default_samplerate"]
                    # Add a marker to indicate which device is currently selected.
                    marker: str = ">" if index == selected_id else " "

                    logger.info(f"{marker} ID {index} - {native_rate}Hz - name: {name}")

            if not input_devices_found:
                logger.warning("No input devices were found on this system.")

        except Exception as e:
            logger.error(f"❌ Could not query audio devices: {e}")
