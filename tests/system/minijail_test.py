
"""Tests for process."""

import os

import mock
from pyfakefs import fake_filesystem_unittest

from bot.system import environment
from bot.system import minijail
from bot.tests.test_libs import helpers as test_helpers


class MinijailTest(fake_filesystem_unittest.TestCase):
  """Minijail tests."""

  def setUp(self):
    """Setup for minijail test."""
    if environment.platform() != 'LINUX':
      self.skipTest('Minijail tests are only applicable for linux platform.')

    self.setUpPyfakefs()
    for subdir in ['dev', 'lib', 'lib32', 'lib64', 'proc']:
      self.fs.create_dir(os.path.join('/', subdir))
    self.fs.create_dir(os.path.join('/', 'usr', 'lib'))
    self.fs.create_dir(os.path.join('/', 'usr', 'lib32'))

    test_helpers.patch(self, [
        'bot.system.minijail._get_minijail_path',
        'bot.system.minijail.MinijailChroot._mknod',
    ])

    test_helpers.patch_environ(self)

    self.mock._get_minijail_path.return_value = '/sbin/minijail'  # pylint: disable=protected-access

  def test_chroot(self):
    """Tests basic chroot setup."""
    chroot_directory = None
    with minijail.MinijailChroot() as chroot:
      chroot_directory = chroot.directory
      self.assertListEqual(
          sorted(os.listdir(chroot_directory)),
          ['dev', 'lib', 'lib32', 'lib64', 'proc', 'tmp', 'usr'])

      self.assertEqual(
          chroot.get_binding(chroot.tmp_directory),
          minijail.ChrootBinding(chroot.tmp_directory, '/tmp', True))

      for directory in ['/lib', '/lib32', '/lib64', '/usr/lib', '/usr/lib32']:
        self.assertEqual(
            chroot.get_binding(directory),
            minijail.ChrootBinding(directory, directory, False))

      self.assertIsNone(chroot.get_binding('/usr'))

    self.assertFalse(os.path.exists(chroot_directory))

  def test_chroot_bindings(self):
    """Tests chroot setup with additional bind dirs."""
    chroot_directory = None
    with minijail.MinijailChroot(bindings=[
        minijail.ChrootBinding('/foo/bar', '/bar', False),
    ]) as chroot:
      chroot_directory = chroot.directory
      self.assertListEqual(
          sorted(os.listdir(chroot_directory)),
          ['bar', 'dev', 'lib', 'lib32', 'lib64', 'proc', 'tmp', 'usr'])

    self.assertEqual(
        chroot.get_binding('/foo/bar'),
        minijail.ChrootBinding('/foo/bar', '/bar', False))
    self.assertFalse(os.path.exists(chroot_directory))

  @mock.patch('bot.system.minijail.os.getuid', lambda: 1000)
  def test_minijail(self):
    """Test minijail process command."""
    with minijail.MinijailChroot() as chroot:
      runner = minijail.MinijailProcessRunner(chroot, '/bin/ls')
      self.assertListEqual(runner.get_command(), [
          '/sbin/minijail', '-U', '-m', '0 1000 1', '-T', 'static', '-c', '0',
          '-n', '-v', '-p', '-l', '-I', '-k', 'proc,/proc,proc,1', '-P',
          chroot.directory, '-b',
          '%s,/tmp,1' % chroot.tmp_directory, '-b', '/lib,/lib,0', '-b',
          '/lib32,/lib32,0', '-b', '/lib64,/lib64,0', '-b',
          '/usr/lib,/usr/lib,0', '-b', '/usr/lib32,/usr/lib32,0', '/bin/ls'
      ])

  @mock.patch('bot.system.minijail.os.getuid', lambda: 1000)
  def test_minijail_bindings(self):
    """Test minijail process command with additional bind dirs."""
    with minijail.MinijailChroot(bindings=[
        minijail.ChrootBinding('/foo/bar', '/bar', True),
        minijail.ChrootBinding('/foo/barr', '/barr', False),
    ]) as chroot:
      runner = minijail.MinijailProcessRunner(chroot, '/bin/ls')
      self.assertListEqual(runner.get_command(), [
          '/sbin/minijail', '-U', '-m', '0 1000 1', '-T', 'static', '-c', '0',
          '-n', '-v', '-p', '-l', '-I', '-k', 'proc,/proc,proc,1', '-P',
          chroot.directory, '-b',
          '%s,/tmp,1' % chroot.tmp_directory, '-b', '/lib,/lib,0', '-b',
          '/lib32,/lib32,0', '-b', '/lib64,/lib64,0', '-b',
          '/usr/lib,/usr/lib,0', '-b', '/usr/lib32,/usr/lib32,0', '-b',
          '/foo/bar,/bar,1', '-b', '/foo/barr,/barr,0', '/bin/ls'
      ])

  @mock.patch('bot.system.minijail.os.getuid', lambda: 1000)
  @mock.patch('bot.system.minijail.subprocess.Popen')
  @mock.patch(
      'bot.system.minijail.tempfile.NamedTemporaryFile')
  def test_minijail_pid(self, mock_tempfile, _):
    """Test minijail process command writing to pid file."""
    mock_tempfile.return_value.name = '/temp_pid'

    with minijail.MinijailChroot() as chroot:
      runner = minijail.MinijailProcessRunner(chroot, 'bin/ls')
      process = runner.run()
      self.assertListEqual(process.command, [
          '/sbin/minijail', '-f', '/temp_pid', '-U', '-m', '0 1000 1', '-T',
          'static', '-c', '0', '-n', '-v', '-p', '-l', '-I', '-k',
          'proc,/proc,proc,1', '-P', chroot.directory, '-b',
          '%s,/tmp,1' % chroot.tmp_directory, '-b', '/lib,/lib,0', '-b',
          '/lib32,/lib32,0', '-b', '/lib64,/lib64,0', '-b',
          '/usr/lib,/usr/lib,0', '-b', '/usr/lib32,/usr/lib32,0', 'bin/ls'
      ])

  @mock.patch('bot.system.minijail.subprocess.Popen')
  def test_minijail_env_vars(self, mock_popen):
    """Test passing of env vars."""
    os.environ['ASAN_OPTIONS'] = 'asan_option=1'
    os.environ['AFL_OPTION'] = 'afl_option=1'
    os.environ['MSAN_OPTIONS'] = 'msan_option=1'
    os.environ['UBSAN_OPTIONS'] = 'ubsan_option=1'
    os.environ['SECRET'] = 'secret'
    os.environ['OTHER'] = 'other'

    with minijail.MinijailChroot() as chroot:
      runner = minijail.MinijailProcessRunner(chroot, 'binary')
      runner.run(env={'MSAN_OPTIONS': 'override=1', 'NAME': 'VALUE'})

      self.assertDictEqual({
          'MSAN_OPTIONS': 'override=1',
          'PATH': '/bin:/usr/bin',
      }, mock_popen.call_args[1]['env'])