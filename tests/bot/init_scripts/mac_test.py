
"""Tests for the Mac initialization script."""

import unittest

import mock

from bot.init_scripts import mac
from bot.tests.test_libs import helpers


class RunTest(unittest.TestCase):
  """Test run."""

  def setUp(self):
    helpers.patch(self, [
        'bot.bot_working_directory.init_scripts.init_runner.run',
        'os.path.expanduser',
        'bot.system.shell.remove_directory',
        'shutil.rmtree',
        'subprocess.Popen',
        'os.path.exists',
    ])
    self.popen = mock.Mock()
    self.stdout = []

    def readline():
      return self.stdout.pop(0)

    self.popen.stdout.readline = readline
    self.mock.Popen.return_value = self.popen

    def expanduser(path):
      return path.replace('~', '/Users/chrome-bot_working_directory')

    self.mock.expanduser.side_effect = expanduser

  def test_run(self):
    """Test run."""
    self.stdout = [
        b'aaaa\n', b'bbbb\n',
        (b'Path: /var/folders/bg/tn9j_qb532s4fz11rzz7m6sc0000gm/0'
         b'//com.apple.LaunchServices-134500.csstore\n'), b'cccc\n', b''
    ]
    mac.run()

    self.mock.exists.return_value = True
    self.mock.rmtree.assert_has_calls([
        mock.call(
            '/var/folders/bg/tn9j_qb532s4fz11rzz7m6sc0000gm/0',
            ignore_errors=True),
        mock.call(
            '/var/folders/bg/tn9j_qb532s4fz11rzz7m6sc0000gm/T',
            ignore_errors=True)
    ])
