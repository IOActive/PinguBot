
"""Tests for corpus_pruning_task."""
import os
import shutil
import tempfile
import unittest

# pylint: disable=unused-argument
import mock

from bot.base import utils
from bot.fuzzers import init as fuzzers_init
from bot.tasks import minimize_task
from bot.datastore import data_handler
from bot.datastore import data_types
from bot.google_cloud_utils import blobs
from bot.system import environment
from bot.tests.test_libs import helpers
from bot.tests.test_libs import test_utils
from bot.tests.test_libs import untrusted_runner_helpers

TEST_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), 'minimize_task_data')


@test_utils.with_cloud_emulators('datastore', 'pubsub')
class LibFuzzerMinimizeTaskTest(unittest.TestCase):
  """libFuzzer Minimize task tests."""

  def setUp(self):
    helpers.patch_environ(self)
    helpers.patch(self, [
        'bot.bot_working_directory.tasks.minimize_task._run_libfuzzer_testcase',
        'bot.bot_working_directory.tasks.minimize_task._run_libfuzzer_tool',
    ])

    test_utils.setup_pubsub(utils.get_application_id())

    environment.set_value('APP_ARGS', '%TESTCASE% fuzz_target')
    environment.set_value('APP_DIR', '/libFuzzer')
    environment.set_value('APP_NAME', '')
    environment.set_value('APP_PATH', '')
    environment.set_value('BOT_TMPDIR', '/bot_tmpdir')
    environment.set_value('CRASH_STACKTRACES_DIR', '/crash_stacks')
    environment.set_value('FUZZER_DIR', '/fuzzer_dir')
    environment.set_value('INPUT_DIR', '/input_dir')
    environment.set_value('JOB_NAME', 'libfuzzer_asan_test')
    environment.set_value('USER_PROFILE_IN_MEMORY', True)

  def test_libfuzzer_skip_minimization_initial_crash_state(self):
    """Test libFuzzer minimization skipping with a valid initial crash state."""
    # TODO(ochang): Fix circular import.
    from bot.crash_analysis.crash_result import CrashResult

    data_types.Job(name='libfuzzer_asan_job').put()
    testcase = data_types.Testcase(
        minimized_keys='',
        fuzzed_keys='FUZZED_KEY',
        job_type='libfuzzer_asan_job',
        security_flag=True)
    testcase.put()

    stacktrace = (
        '==14970==ERROR: AddressSanitizer: heap-buffer-overflow on address '
        '0x61b00001f7d0 at pc 0x00000064801b bp 0x7ffce478dbd0 sp '
        '0x7ffce478dbc8 READ of size 4 at 0x61b00001f7d0 thread T0\n'
        '#0 0x64801a in frame0() src/test.cpp:1819:15\n'
        '#1 0x647ac5 in frame1() src/test.cpp:1954:25\n'
        '#2 0xb1dee7 in frame2() src/test.cpp:160:9\n'
        '#3 0xb1ddd8 in frame3() src/test.cpp:148:34\n')
    self.mock._run_libfuzzer_testcase.return_value = CrashResult(  # pylint: disable=protected-access
        1, 1.0, stacktrace)

    self.mock._run_libfuzzer_tool.return_value = (None, None)  # pylint: disable=protected-access

    minimize_task.do_libfuzzer_minimization(testcase, '/testcase_file_path')

    testcase = data_handler.get_testcase_by_id(testcase.key.id())
    self.assertEqual('Heap-buffer-overflow', testcase.crash_type)
    self.assertEqual('frame0\nframe1\nframe2\n', testcase.crash_state)
    self.assertEqual('0x61b00001f7d0', testcase.crash_address)
    self.assertEqual(
        '+----------------------------------------Release Build Stacktrace'
        '----------------------------------------+\n%s' % stacktrace,
        testcase.crash_stacktrace)


class MinimizeTaskTestUntrusted(
    untrusted_runner_helpers.UntrustedRunnerIntegrationTest):
  """Minimize task tests for untrusted."""

  def setUp(self):
    """Set up."""
    super().setUp()
    environment.set_value('JOB_NAME', 'libfuzzer_asan_job')

    patcher = mock.patch(
        'bot.bot_working_directory.fuzzers.libFuzzer.fuzzer.LibFuzzer.fuzzer_directory',
        new_callable=mock.PropertyMock)

    mock_fuzzer_directory = patcher.start()
    self.addCleanup(patcher.stop)

    mock_fuzzer_directory.return_value = os.path.join(
        environment.get_value('ROOT_DIR'), 'src', 'clusterfuzz', '_internal',
        'bot_working_directory', 'fuzzers', 'libFuzzer')

    job = data_types.Job(
        name='libfuzzer_asan_job',
        environment_string=(
            'RELEASE_BUILD_BUCKET_PATH = '
            'gs://clusterfuzz-test-data/test_libfuzzer_builds/'
            'test-libFuzzer-build-([0-9]+).zip\n'
            'REVISION_VARS_URL = https://commondatastorage.googleapis.com/'
            'clusterfuzz-test-data/test_libfuzzer_builds/'
            'test-libFuzzer-build-%s.srcmap.json\n'))
    job.put()

    data_types.FuzzTarget(
        engine='libFuzzer', binary='test_fuzzer', project='test-project').put()
    data_types.FuzzTargetJob(
        fuzz_target_name='libFuzzer_test_fuzzer',
        engine='libFuzzer',
        job='libfuzzer_asan_job').put()

    environment.set_value('USE_MINIJAIL', True)
    data_types.Fuzzer(
        revision=1,
        file_size='builtin',
        source='builtin',
        name='libFuzzer',
        max_testcases=4,
        builtin=True).put()
    self.temp_dir = tempfile.mkdtemp(dir=environment.get_value('FUZZ_INPUTS'))

  def tearDown(self):
    super().tearDown()
    shutil.rmtree(self.temp_dir, ignore_errors=True)

  def test_minimize(self):
    """Test minimize."""
    helpers.patch(self, ['bot.base.utils.is_oss_fuzz'])
    self.mock.is_oss_fuzz.return_value = True

    testcase_file_path = os.path.join(self.temp_dir, 'testcase')
    with open(testcase_file_path, 'wb') as f:
      f.write(b'EEE')

    with open(testcase_file_path) as f:
      fuzzed_keys = blobs.write_blob(f)

    testcase_path = os.path.join(self.temp_dir, 'testcase')

    testcase = data_types.Testcase(
        crash_type='Null-dereference WRITE',
        crash_address='',
        crash_state='Foo\n',
        crash_stacktrace='',
        crash_revision=1337,
        fuzzed_keys=fuzzed_keys,
        fuzzer_name='libFuzzer',
        overridden_fuzzer_name='libFuzzer_test_fuzzer',
        job_type='libfuzzer_asan_job',
        absolute_path=testcase_path,
        minimized_arguments='%TESTCASE% test_fuzzer')
    testcase.put()

    data_types.FuzzTarget(engine='libFuzzer', binary='test_fuzzer').put()

    fuzzers_init.run()

    self._setup_env(job_type='libfuzzer_asan_job')
    environment.set_value('APP_ARGS', testcase.minimized_arguments)
    environment.set_value('LIBFUZZER_MINIMIZATION_ROUNDS', 3)
    environment.set_value('UBSAN_OPTIONS',
                          'unneeded_option=1:silence_unsigned_overflow=1')
    minimize_task.execute_task(testcase.key.id(), 'libfuzzer_asan_job')

    testcase = data_handler.get_testcase_by_id(testcase.key.id())
    self.assertNotEqual('', testcase.minimized_keys)
    self.assertNotEqual('NA', testcase.minimized_keys)
    self.assertNotEqual(testcase.fuzzed_keys, testcase.minimized_keys)
    self.assertEqual({
        'ASAN_OPTIONS': {},
        'UBSAN_OPTIONS': {
            'silence_unsigned_overflow': 1
        }
    }, testcase.get_metadata('env'))

    blobs.read_blob_to_disk(testcase.minimized_keys, testcase_path)

    with open(testcase_path, 'rb') as f:
      self.assertEqual(1, len(f.read()))