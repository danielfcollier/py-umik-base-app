"""
Provides utility functions for generating timestamps.

Author: Daniel Collier
GitHub: https://github.com/danielfcollier
Year: 2025
"""

from datetime import datetime


class DatetimeStamp:
    @staticmethod
    def get():
        now = datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        return timestamp
