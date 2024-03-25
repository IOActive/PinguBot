
"""Android init scripts."""
from bot.init_scripts import init_runner
from bot.platforms import android
from bot.system import environment

TIME_SINCE_REBOOT_MIN_THRESHOLD = 30 * 60  # 30 minutes.


def run():
    """Run Android initialization."""
    init_runner.run()

    # Set cuttlefish device serial if needed.
    if environment.is_android_cuttlefish():
        android.adb.set_cuttlefish_device_serial()

    # Check if we need to reflash device to latest build.
    android.flash.flash_to_latest_build_if_needed()

    # Reconnect to cuttlefish device if connection is ever lost.
    if environment.is_android_cuttlefish():
        android.adb.connect_to_cuttlefish_device()

    # Reboot to bring device in a good state if not done recently.
    if android.adb.time_since_last_reboot() > TIME_SINCE_REBOOT_MIN_THRESHOLD:
        android.device.reboot()

    # Make sure that device is in a good condition before we move forward.
    android.adb.wait_until_fully_booted()

    # Wait until battery charges to a minimum level and temperature threshold.
    android.battery.wait_until_good_state()

    # Initialize environment settings.
    android.device.initialize_environment()
