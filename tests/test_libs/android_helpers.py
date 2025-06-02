
"""Test helpers for Android."""

import unittest

from pingu_sdk.platforms.android import adb
from pingu_sdk.system import environment
from tests.test_libs import helpers, test_utils


@test_utils.android_device_required
class AndroidTest(unittest.TestCase):
  """Set up state for Android tests."""

  def setUp(self):
    helpers.patch_environ(self)
    environment.set_value('OS_OVERRIDE', 'ANDROID')
    environment.set_bot_environment()
    adb.setup_adb()
    adb.run_as_root()
