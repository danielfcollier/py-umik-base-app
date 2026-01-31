"""
Shared pytest fixtures for umik_base_app tests.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

import threading
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def stop_event():
    """A threading.Event for coordinating thread shutdown in tests."""
    return threading.Event()


@pytest.fixture
def mock_transport():
    """A mock AudioTransport for injection into components."""
    return MagicMock()
