
"""Date or time helper functions."""

import time

from bot.utils import utils


def initialize_timezone_from_environment():
    """Initializes timezone for date functions based on environment."""
    #plt = environment.platform()
    #if plt == 'WINDOWS':
    #    return

    # Only available on Unix platforms.
    time.tzset()


def time_has_expired(timestamp,
                     compare_to=None,
                     days=0,
                     hours=0,
                     minutes=0,
                     seconds=0):
    """Checks to see if a timestamp is older than another by a certain amount."""
    if compare_to is None:
        compare_to = utils.utcnow()

    total_time = days * 3600 * 24 + hours * 3600 + minutes * 60 + seconds
    return (compare_to - timestamp).total_seconds() > total_time
