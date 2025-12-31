""" "
Enum representing the operational mode of the application.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from enum import Enum


class OperationalMode(Enum):
    """
    Enum representing the operational mode of the application.
    """

    MONOLITHIC = "monolithic"
    PRODUCER = "producer"
    CONSUMER = "consumer"

    @staticmethod
    def from_string(mode_str: str) -> "OperationalMode":
        """
        Convert a string to an OperationalMode enum member.

        :param mode_str: The string representation of the operational mode.
        :return: Corresponding OperationalMode enum member.
        :raises ValueError: If the string does not match any enum member.
        """
        try:
            return OperationalMode(mode_str.lower())
        except ValueError as e:
            raise ValueError(f"Invalid operational mode: {mode_str}") from e

    @staticmethod
    def is_monolithic(mode_str: str) -> bool:
        """
        Check if the operational mode is monolithic.

        :return: True if the mode is MONOLITHIC, False otherwise.
        """
        return OperationalMode.from_string(mode_str) == OperationalMode.MONOLITHIC

    @staticmethod
    def is_producer(mode_str: str) -> bool:
        """
        Check if the operational mode is producer.

        :return: True if the mode is PRODUCER, False otherwise.
        """
        return OperationalMode.from_string(mode_str) == OperationalMode.PRODUCER

    @staticmethod
    def is_consumer(mode_str: str) -> bool:
        """
        Check if the operational mode is consumer.

        :return: True if the mode is CONSUMER, False otherwise.
        """
        return OperationalMode.from_string(mode_str) == OperationalMode.CONSUMER
