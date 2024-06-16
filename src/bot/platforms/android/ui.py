
"""UI related functions."""

import time

from . import adb


def clear_notifications():
    """Clear all pending notifications."""
    adb.run_shell_command(['service', 'call', 'notification', '1'])


def unlock_screen():
    """Unlocks the screen if it is locked."""
    window_dump_output = adb.run_shell_command(['dumpsys', 'window'])
    if 'mShowingLockscreen=true' not in window_dump_output:
        # Screen is not locked, no work to do.
        return

    # Quick power on and off makes this more reliable.
    adb.run_shell_command(['input', 'keyevent', 'KEYCODE_POWER'])
    adb.run_shell_command(['input', 'keyevent', 'KEYCODE_POWER'])

    # This key does the unlock.
    adb.run_shell_command(['input', 'keyevent', 'KEYCODE_MENU'])

    # Artificial delay to let the unlock to complete.
    time.sleep(1)
