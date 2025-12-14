"""
Unit tests for FilterCacheStrategy implementations.
"""

from unittest.mock import patch

import numpy as np

from src.library.cache_strategy import FileFilterCache, NoOpFilterCache


def test_file_cache_load_success():
    """Test loading existing file via numpy."""
    cache = FileFilterCache()
    fake_data = np.array([1, 2, 3])

    with patch("os.path.exists", return_value=True):
        with patch("numpy.load", return_value=fake_data) as mock_load:
            result = cache.load("dummy.npy")

            mock_load.assert_called_once_with("dummy.npy")
            assert np.array_equal(result, fake_data)


def test_file_cache_load_missing():
    """Test load returns None if file doesn't exist."""
    cache = FileFilterCache()

    with patch("os.path.exists", return_value=False):
        result = cache.load("missing.npy")
        assert result is None


def test_file_cache_save_exception():
    """Test that save handles exceptions gracefully (logs error, doesn't crash)."""
    cache = FileFilterCache()
    data = np.zeros(5)

    with patch("numpy.save", side_effect=PermissionError("Boom")):
        # Should not raise exception
        cache.save("protected.npy", data)


def test_noop_cache():
    """Test that NoOp cache does nothing."""
    cache = NoOpFilterCache()
    assert cache.load("anything") is None
    cache.save("anything", np.zeros(1))
