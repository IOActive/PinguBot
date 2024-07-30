
"""Tests for init_runner."""

import unittest

from bot.init_scripts import init_runner
from bot.tests.test_libs import helpers


class InitRunnerTest(unittest.TestCase):
  """Tests for init_runner."""

  def setUp(self):
    helpers.patch(self, [
        'bot.system.environment.platform',
        'bot.system.process_handler.run_process',
    ])

  def test_windows(self):
    """Test windows."""
    self.mock.platform.return_value = 'WINDOWS'
    init_runner.run()
    self.mock.run_process.assert_called_with(
        'powershell.exe ./configs/test/bot_working_directory/init/windows.ps1',
        ignore_children=True,
        need_shell=True,
        testcase_run=False,
        timeout=1800)

  def test_posix(self):
    """Test posix."""
    self.mock.platform.return_value = 'LINUX'
    init_runner.run()
    self.mock.run_process.assert_called_with(
        './configs/test/bot_working_directory/init/linux.bash',
        ignore_children=True,
        need_shell=True,
        testcase_run=False,
        timeout=1800)

  def test_nonexistent_platform(self):
    """Test posix."""
    self.mock.platform.return_value = 'FAKE'
    init_runner.run()
    self.assertEqual(0, self.mock.run_process.call_count)
