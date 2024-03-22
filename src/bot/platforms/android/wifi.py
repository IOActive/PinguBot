
"""Wifi related functions."""

import os
import time

from ...metrics import logs
from ...system import environment

try:
    from shlex import quote
except ImportError:
    from pipes import quote

from . import adb
from . import app

WIFI_UTIL_PACKAGE_NAME = 'com.android.tradefed.utils.wifi'
WIFI_UTIL_CALL_PATH = '%s/.WifiUtil' % WIFI_UTIL_PACKAGE_NAME


def disable():
    """Disable wifi."""
    adb.run_shell_command(['svc', 'wifi', 'disable'])


def enable():
    """Enable wifi."""
    adb.run_shell_command(['svc', 'wifi', 'enable'])


def disable_airplane_mode():
    """Disable airplane mode."""
    adb.run_shell_command(['settings', 'put', 'global', 'airplane_mode_on', '0'])
    adb.run_shell_command([
        'am', 'broadcast', '-a', 'android.intent.action.AIRPLANE_MODE', '--ez',
        'state', 'false'
    ])


def configure(force_enable=False):
    """Configure airplane mode and wifi on device."""
    # The reproduce tool shouldn't inherit wifi settings from jobs.
    if environment.get_value('REPRODUCE_TOOL'):
        return

    # Airplane mode should be disabled in all cases. This can get inadvertently
    # turned on via gestures.
    disable_airplane_mode()

    # Need to disable wifi before changing configuration.
    disable()

    # Check if wifi needs to be enabled. If not, then no need to modify the
    # supplicant file.
    wifi_enabled = force_enable or environment.get_value('WIFI', True)
    if not wifi_enabled:
        # No more work to do, we already disabled it at start.
        return

    # Wait 2 seconds to allow the wifi to be enabled.
    enable()
    time.sleep(2)

    # Install helper apk to configure wifi.
    wifi_util_apk_path = os.path.join(
        environment.get_platform_resources_directory(), 'wifi_util.apk')
    if not app.is_installed(WIFI_UTIL_PACKAGE_NAME):
        app.install(wifi_util_apk_path)

    # Get ssid and password from admin configuration.
    if environment.is_android_cuttlefish():
        wifi_ssid = 'VirtWifi'
        wifi_password = ''
    else:
        config = db_config.get()
        if not config.wifi_ssid:
            logs.log('No wifi ssid is set, skipping wifi config.')
            return
        wifi_ssid = config.wifi_ssid
        wifi_password = config.wifi_password or ''

    connect_wifi_command = (
        'am instrument -e method connectToNetwork -e ssid {ssid} ')
    if wifi_password:
        connect_wifi_command += '-e psk {password} '
    connect_wifi_command += '-w {call_path}'

    output = adb.run_shell_command(
        connect_wifi_command.format(
            ssid=quote(wifi_ssid),
            password=quote(wifi_password),
            call_path=WIFI_UTIL_CALL_PATH))
    if 'result=true' not in output:
        logs.log_warn('Failed to connect to wifi.', output=output)