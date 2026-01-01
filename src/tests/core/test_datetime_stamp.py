"""
Unit tests for DatetimeStamp.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from datetime import datetime
from unittest.mock import patch

from umik_base_app import DatetimeStamp


def test_get_timestamp_format():
    """Verify that the timestamp follows 'YYYY-MM-DD HH:MM:SS' format."""
    # Mock a fixed datetime
    fixed_date = datetime(2025, 1, 1, 12, 0, 0)

    with patch("umik_base_app.datetime_stamp.datetime.datetime") as mock_datetime:
        mock_datetime.now.return_value = fixed_date

        timestamp = DatetimeStamp.get()
        assert timestamp == "2025-01-01 12:00:00"
