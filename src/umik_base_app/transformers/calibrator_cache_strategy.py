"""
Defines strategies for caching filter coefficients.

This module allows decoupling the persistence logic (file I/O) from the
CalibratorTransformer, facilitating unit testing without side effects (file creation).

Author: Daniel Collier
Year: 2025
"""

import logging
import os
from typing import Protocol, runtime_checkable

import numpy as np

logger = logging.getLogger(__name__)


@runtime_checkable
class CalibratorCacheStrategy(Protocol):
    """
    Protocol for caching and retrieving numpy arrays (filter taps).
    """

    def load(self, key: str) -> np.ndarray | None:
        """
        Retrieves data associated with the key.
        Returns None if the key does not exist or data cannot be loaded.
        """
        ...

    def save(self, key: str, data: np.ndarray) -> None:
        """
        Saves the data using the provided key.
        """
        ...


class FileCalibratorCache:
    """
    Concrete implementation that saves/loads filters to the filesystem.
    The 'key' is expected to be a valid file path.
    """

    def load(self, key: str) -> np.ndarray | None:
        """
        Loads a numpy array from a file path.
        """
        if not os.path.exists(key):
            return None

        try:
            logger.info(f"Found cached filter at '{key}'. Loading...")
            return np.load(key)
        except Exception as e:
            logger.warning(f"Failed to load cached filter from '{key}'. Error: {e}")
            return None

    def save(self, key: str, data: np.ndarray) -> None:
        """
        Saves a numpy array to a file path.
        """
        try:
            np.save(key, data)
            logger.debug(f"Saved filter to cache at '{key}'.")
        except Exception as e:
            logger.error(f"Failed to save filter cache to '{key}'. Error: {e}")


class NoOpCalibratorCache:
    """
    A dummy implementation for testing that does nothing.
    Ensures no files are created during tests.
    """

    def load(self, key: str) -> np.ndarray | None:
        return None

    def save(self, key: str, data: np.ndarray) -> None:
        pass
