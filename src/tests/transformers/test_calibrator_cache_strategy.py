"""
Unit tests for CalibratorCacheStrategy implementations.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import patch, sentinel

from umik_base_app.transformers.calibrator_cache_strategy import FileCalibratorCache, NoOpCalibratorCache


def test_file_cache_load_success():
    """Test loading existing file via numpy."""
    cache = FileCalibratorCache()

    with patch("os.path.exists", return_value=True):
        with patch("numpy.load", return_value=sentinel.cal_data) as mock_load:
            result = cache.load(sentinel.file_path)

            mock_load.assert_called_once_with(sentinel.file_path)
            assert result is sentinel.cal_data


def test_file_cache_load_missing():
    """Test load returns None if file doesn't exist."""
    cache = FileCalibratorCache()

    with patch("os.path.exists", return_value=False):
        result = cache.load(sentinel.file_path)
        assert result is None


def test_file_cache_save_exception():
    """Test that save handles exceptions gracefully (logs error, doesn't crash)."""
    cache = FileCalibratorCache()

    with patch("numpy.save", side_effect=PermissionError("Boom")):
        # Should not raise exception
        cache.save(sentinel.file_path, sentinel.cal_data)


def test_noop_cache():
    """Test that NoOp cache does nothing."""
    cache = NoOpCalibratorCache()
    assert cache.load(sentinel.file_path) is None
    # Verify save accepts arguments without error
    cache.save(sentinel.file_path, sentinel.cal_data)
