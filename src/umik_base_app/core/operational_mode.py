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

