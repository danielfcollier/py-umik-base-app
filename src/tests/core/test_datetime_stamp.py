"""
Unit tests for DatetimeStamp.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from unittest.mock import Mock, patch, sentinel

from umik_base_app import DatetimeStamp


def test_get_timestamp_format():
    """Verify that the timestamp follows 'YYYY-MM-DD HH:MM:SS' format."""
    with patch("umik_base_app.core.datetime_stamp.datetime") as mock_datetime:
        # Arrange:
        mock_now_obj = Mock()
        mock_datetime.now.return_value = mock_now_obj
        mock_now_obj.strftime.return_value = sentinel.timestamp

        # Act
        result = DatetimeStamp.get()

        # Assert
        assert result == sentinel.timestamp
        mock_datetime.now.assert_called_once()
        mock_now_obj.strftime.assert_called_once_with("%Y-%m-%d %H:%M:%S")
