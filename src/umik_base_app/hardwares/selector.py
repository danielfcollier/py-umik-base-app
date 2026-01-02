"""
A module for discovering and selecting audio input devices (microphones)
using the sounddevice library. It provides a robust class to automatically
select the system's default microphone or find a specific one by name.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from __future__ import annotations

import logging

import sounddevice as sd

from ..settings import get_settings  # Import settings

logger = logging.getLogger(__name__)
settings = get_settings()  # Load settings


class HardwareNotFound(Exception):
    """Custom exception raised when a specified audio device cannot be found."""

    def __init__(self, message: str):
        self.message = message
        super().__init__(self.message)


class HardwareSelector:
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

        HardwareSelector.show_audio_devices(self.id)

    @staticmethod
    def find_device_by_name(name_substring: str | None = None) -> int | None:
        """
        Searches for the first input device that contains the given substring in its name.
        If no name is provided, uses the TARGET_DEVICE_NAME from settings.

        :param name_substring: The string to search for (case-insensitive). Defaults to settings.
        :return: The device ID (index) if found, otherwise None.
        """
        target = name_substring if name_substring else settings.HARDWARE.TARGET_DEVICE_NAME

        try:
            audio_devices = list(sd.query_devices())
            for device in audio_devices:
                if device["max_input_channels"] > 0 and target.lower() in device["name"].lower():
                    return device["index"]
        except Exception as e:
            logger.error(f"Error searching for device '{target}': {e}")
        return None

    def _get_audio_device(self, target_id: int | None = None) -> dict:
        """
        Queries the system for available devices and returns the desired one.

        :param target_id: The ID of the device to search for.
        :return: A dictionary containing the device's information.
        :raises HardwareNotFound: If the target_id device is not found.
        """
        try:
            audio_devices: list[dict] = list(sd.query_devices())
        except Exception as e:
            logger.error(f"❌ An unexpected error occurred while querying audio devices: {e}")
            raise

        default_audio_device_id = sd.default.device[0]

        if not target_id:
            logger.warning(f"No target specified. Selecting default input device (ID: {default_audio_device_id})...")
            # Find the default device in the list
            default_device = next(
                filter(lambda device: device["index"] == default_audio_device_id, audio_devices), None
            )

            if default_device is None:
                raise HardwareNotFound(
                    message=f"System default device (ID: {default_audio_device_id}) not found in device list."
                )

            return default_device

        logger.debug(f"Searching for an input device index '{target_id}'...")
        target_audio_device: dict | None = next(
            filter(lambda device: target_id == device["index"] and device["max_input_channels"] > 0, audio_devices),
            None,
        )

        if target_audio_device is None:
            logger.warning("Failed to select audio device.", exc_info=True)
            raise HardwareNotFound(message=f"Device with ID {target_id} not found.")

        target_name = target_audio_device["name"]
        logger.info(f"✅ Selected audio device: ID={target_id}, Name={target_name}")

        return target_audio_device

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

                    logger.info(f"{marker} ID {index} - {native_rate:.0f}Hz - name: {name}")

            if not input_devices_found:
                logger.warning("No input devices were found on this system.")

        except Exception as e:
            logger.error(f"❌ Could not query audio devices: {e}")
