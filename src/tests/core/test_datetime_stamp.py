"""
Unit tests for DatetimeStamp.
"""

from datetime import datetime
from unittest.mock import patch

from src.py_umik.core.datetime_stamp import DatetimeStamp


def test_get_timestamp_format():
    """Verify that the timestamp follows 'YYYY-MM-DD HH:MM:SS' format."""
    # Mock a fixed datetime
    fixed_date = datetime(2025, 1, 1, 12, 0, 0)

    with patch("src.py_umik.core.datetime_stamp.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_date

        timestamp = DatetimeStamp.get()
        assert timestamp == "2025-01-01 12:00:00"
