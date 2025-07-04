
"""Tests for the Windows initialization script."""

import unittest

import mock

from bot.init_scripts import windows
from pingu_sdk.system import environment
from tests.test_libs import helpers


class CleanTempDirectoriesTest(unittest.TestCase):
  """Test clean_temp_directories."""

  def setUp(self):
    helpers.patch(self, [
        'os.path.abspath',
        'os.path.expandvars',
        'os.path.join',
        'pingu_sdk.system.shell.remove_directory',
    ])

    def abspath(path):
      return path

    def expandvars(path):
      path = path.replace('%TEMP%', r'C:\Users\clusterfuzz\AppData\Local\Temp')
      path = path.replace('%USERPROFILE%', r'C:\Users\clusterfuzz')
      path = path.replace('%WINDIR%', r'C:\WINDOWS')
      return path

    def join(path1, path2):
      """Windows specific os.path.join"""
      return r'%s\%s' % (path1.rstrip('\\'), path2)

    self.mock.abspath.side_effect = abspath
    self.mock.expandvars.side_effect = expandvars
    self.mock.join.side_effect = join

  def test(self):
    windows.clean_temp_directories()

    self.mock.remove_directory.assert_has_calls([
        mock.call(
            r'C:\Users\clusterfuzz\AppData\Local\Temp',
            recreate=True,
            ignore_errors=True),
        mock.call(
            r'C:\Users\clusterfuzz\AppVerifierLogs',
            recreate=True,
            ignore_errors=True),
        mock.call(
            r'C:\Users\clusterfuzz\Downloads',
            recreate=True,
            ignore_errors=True),
        mock.call(r'C:\WINDOWS\Temp', recreate=True, ignore_errors=True),
        mock.call(
            r'C:\Program Files (x86)\Windows Kits\10\Debuggers\x86\sym',
            recreate=True,
            ignore_errors=True),
        mock.call(
            r'C:\Program Files (x86)\Windows Kits\10\Debuggers\x64\sym',
            recreate=True,
            ignore_errors=True)
    ])


class RemountIfNeededTest(unittest.TestCase):
  """Test remount_if_needed."""

  def setUp(self):
    helpers.patch_environ(self)
    helpers.patch(self, [
        'pingu_sdk.metrics.logs.log_error',
        'pingu_sdk.system.retry.sleep',
        'pingu_sdk.utils.utils.write_data_to_file',
        'os.path.exists',
        'os.path.join',
        'subprocess.call',
        'subprocess.check_call',
    ])

    def join(path1, path2):
      """Windows specific os.path.join"""
      return r'%s\%s' % (path1.rstrip('\\'), path2)

    self.mock.join.side_effect = join

    environment.set_value('NFS_HOST', 'clusterfuzz-windows-0001')
    environment.set_value('NFS_VOLUME', 'cfvolume')
    environment.set_value('NFS_ROOT', 'X:\\')

  def test_with_mount_and_with_check_file(self):
    """Test remount_if_needed when mount works and check file already exists."""
    self.mock.exists.return_value = True
    windows.remount_if_needed()

    self.assertEqual(0, self.mock.call.call_count)
    self.assertEqual(0, self.mock.check_call.call_count)
    self.assertEqual(0, self.mock.write_data_to_file.call_count)

  def test_without_mount_and_without_check_file_no_retry(self):
    """Test remount_if_needed when mount and check file do not exist and gets
    created later on successful remount."""
    self.mock.exists.side_effect = [False, False, True]
    windows.remount_if_needed()

    self.mock.call.assert_called_once_with(['umount', '-f', 'X:\\'])
    self.mock.check_call.assert_called_once_with([
        'mount', '-o', 'anon', '-o', 'nolock', '-o', 'retry=10',
        'clusterfuzz-windows-0001:/cfvolume', 'X:\\'
    ])
    self.mock.write_data_to_file.assert_called_once_with('ok', r'X:\check')

  def test_without_mount_and_with_check_file_no_retry(self):
    """Test remount_if_needed when mount does not exist, but check file does and
    check file does not get recreated later on successful remount."""
    self.mock.exists.side_effect = [False, True]
    windows.remount_if_needed()

    self.mock.call.assert_called_once_with(['umount', '-f', 'X:\\'])
    self.mock.check_call.assert_called_once_with([
        'mount', '-o', 'anon', '-o', 'nolock', '-o', 'retry=10',
        'clusterfuzz-windows-0001:/cfvolume', 'X:\\'
    ])
    self.assertEqual(0, self.mock.write_data_to_file.call_count)

  def test_without_mount_and_without_check_file_retry(self):
    """Test remount_if_needed when check file does not exist and gets created
    later on second remount try."""
    self.mock.exists.side_effect = [False, False, False, False, True]
    windows.remount_if_needed()

    self.mock.call.assert_has_calls([mock.call(['umount', '-f', 'X:\\'])] * 2)
    self.mock.check_call.assert_has_calls([
        mock.call([
            'mount', '-o', 'anon', '-o', 'nolock', '-o', 'retry=10',
            'clusterfuzz-windows-0001:/cfvolume', 'X:\\'
        ])
    ] * 2)
    self.mock.write_data_to_file.assert_called_once_with('ok', r'X:\check')

  def test_without_check_file_fail(self):
    """Test remount_if_needed when check file does not exist and does not get
    recreated due to remount failure."""
    self.mock.exists.side_effect = [False, False, False] * 6

    with self.assertRaises(Exception):
      windows.remount_if_needed()

    self.mock.call.assert_has_calls([mock.call(['umount', '-f', 'X:\\'])] * 6)
    self.mock.check_call.assert_has_calls([
        mock.call([
            'mount', '-o', 'anon', '-o', 'nolock', '-o', 'retry=10',
            'clusterfuzz-windows-0001:/cfvolume', 'X:\\'
        ])
    ] * 6)
    self.mock.write_data_to_file.assert_has_calls(
        [mock.call('ok', r'X:\check')] * 6)
