
"""Tests for init_runner."""

import os
import unittest

from bot.init_scripts import init_runner
from tests.test_libs import helpers


class InitRunnerTest(unittest.TestCase):
  """Tests for init_runner."""

  def setUp(self):
    helpers.patch(self, [
        'pingu_sdk.system.environment.platform',
        'pingu_sdk.system.process_handler.run_process',
    ])

  def test_windows(self):
    """Test windows."""
    self.mock.platform.return_value = 'WINDOWS'
    init_runner.run()
    expected_path = os.path.abspath('./config/bot/init/windows.ps1')
    self.mock.run_process.assert_called_with(
        f"powershell.exe {expected_path}",
        ignore_children=True,
        need_shell=True,
        testcase_run=False,
        timeout=1800)

  def test_posix(self):
    """Test posix."""
    self.mock.platform.return_value = 'LINUX'
    init_runner.run()
    expected_path = os.path.abspath('./config/bot/init/linux.bash')
    self.mock.run_process.assert_called_with(
        expected_path,
        ignore_children=True,
        need_shell=True,
        testcase_run=False,
        timeout=1800)

  def test_nonexistent_platform(self):
    """Test posix."""
    self.mock.platform.return_value = 'FAKE'
    init_runner.run()
    self.assertEqual(0, self.mock.run_process.call_count)
