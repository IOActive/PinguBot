
"""Tests for setup."""

import datetime
import json
import os
import subprocess
import unittest
from uuid import uuid4

import mock
from pyfakefs import fake_filesystem_unittest

from pingu_sdk.build_management import revisions
from bot.tasks import setup
from pingu_sdk.datastore import data_handler
from pingu_sdk.datastore.pingu_api import JobApi, FuzzerApi
from pingu_sdk.system import environment
from pingu_sdk.datastore import blobs_manager as blobs
from tests.test_libs import helpers as test_helpers
from tests.test_libs import test_utils
import pyfakefs.fake_filesystem_unittest as fake_fs_unittest
from pingu_sdk.datastore.models import Fuzzer, Job, Testcase

class update(fake_fs_unittest.TestCase):
  def setUp(self):
    test_helpers.patch_environ(self)
    test_utils.set_up_pyfakefs(self)

    test_helpers.patch(self, [
        'pingu_sdk.fuzzers.engine_common.unpack_seed_corpus_if_needed',
        'pingu_sdk.datastore.pingu_api.fuzzer_api.FuzzerApi.download_fuzzer',
        'pingu_sdk.utils.utils.write_data_to_file'
    ])

    self.fs.create_dir('/inputs')
    self.fs.create_dir('/fuzzer')
    self.fs.create_file('/path/target')

    os.environ['FAIL_RETRIES'] = '1'
    os.environ['FUZZ_INPUTS_DISK'] = '/inputs'
    os.environ['FUZZERS_DIR'] = '/fuzzer'
    class mockOut:
      def __enter__(self):
          return []

      def __exit__(self, type, value, traceback):
          pass
    class mockPopen:
      def __init__(self):
          self.stdout = mockOut()

      def wait(self):
          return 0
    
    subprocess.Popen = lambda *args, **kwargs : mockPopen()

    FuzzerApi.get_fuzzer = mock.MagicMock()
    self.mock_fuzzer = Fuzzer(
        id=uuid4(),  # Use a random UUID for the mock fuzzer ID
        name="MockFuzzer",
        filename="mock_fuzzer.zip",
        file_size=1024 * 1024,  # Size in bytes (1 MB)
        blobstore_path="test-fuzzers-bucket/mock_fuzzer.zip",
        executable_path="pythonfuzz-master/pythonfuzz",
        timeout=60,  # Seconds
        supported_platforms='Linux',
        launcher_script="launch_script.sh",
        install_script="",
        jobs="unspecified",
        max_testcases=2000,
        additional_environment_string="FUZZER_OPTIONS=--mock-mode",
        stats_columns=json.dumps({
            'coverage': 'Coverage',
            'execution_time': 'Execution Time',
            'crash_rate': 'Crash Rate'
        }),
        stats_column_descriptions=json.dumps({
            'coverage': 'Percentage of code executed by the fuzzer.',
            'execution_time': 'Average time taken to run a testcase in seconds.',
            'crash_rate': 'Number of crashes per thousand testcases.'
        }),
        builtin=False,
        differential=False,
        has_large_testcases=True,
        result="Generated 1500 testcases.",
        result_timestamp=datetime.datetime.utcnow(),  # Use the current UTC time for the timestamp
        console_output="Fuzzer run completed successfully.",
        return_code=0,
        sample_testcase="gs://mock-bucket/mock_fuzzer_sample.txt",
        revision=1.2,
        data_bundle_name="Mock Fuzzer Data Bundle"
    )
    FuzzerApi.get_fuzzer.return_value = self.mock_fuzzer
    revisions.needs_update = mock.MagicMock()
    revisions.needs_update.return_value = True
    os.environ['DATA_BUNDLES_DIR'] = '/inputs'

    def copy_file_from_side_effect(content, file_path):
      self.fs.add_real_file(source_path="tests/bot/tasks/test_fuzzers/blackbox_fuzzing_test.zip", target_path=file_path)
      return True
    
    self.mock.download_fuzzer.return_value = b'fake fuzzer package'
    self.mock.write_data_to_file.side_effect = copy_file_from_side_effect

  def test_update_fuzzer_and_data_bundles(self):
    fuzzer_name = "fuzzer"
    setup.update_fuzzer_and_data_bundles(self.mock_fuzzer)
    pass

class IsDirectoryOnNfsTest(unittest.TestCase):
  """Tests for the is_directory_on_nfs function."""

  def setUp(self):
    environment.set_value('NFS_ROOT', '/nfs')

  def tearDown(self):
    environment.remove_key('NFS_ROOT')

  def test_is_directory_on_nfs_without_nfs(self):
    """Test is_directory_on_nfs without nfs."""
    environment.remove_key('NFS_ROOT')
    self.assertFalse(setup.is_directory_on_nfs('/nfs/dir1'))

  def test_is_directory_on_nfs_with_nfs_and_data_bundle_on_nfs(self):
    """Test is_directory_on_nfs with nfs and data bundle on nfs."""
    self.assertTrue(setup.is_directory_on_nfs('/nfs/dir1'))

  def test_is_directory_on_nfs_with_nfs_and_data_bundle_on_local(self):
    """Test is_directory_on_nfs with nfs and data bundle on local."""
    self.assertFalse(setup.is_directory_on_nfs('/tmp/dir1'))


# pylint: disable=protected-access
class GetApplicationArgumentsTest(unittest.TestCase):
  """Tests _get_application_arguments."""

  def setUp(self):
    test_helpers.patch_environ(self)

    '''Job(
        name='linux_asan_chrome',
        environment_string=('APP_ARGS = --orig-arg1 --orig-arg2')).put()
    Job(
        name='linux_msan_chrome_variant',
        environment_string=(
            'APP_ARGS = --arg1 --arg2 --arg3="--flag1 --flag2"')).put()

    Job(name='libfuzzer_asan_chrome', environment_string=('')).put()
    Job(
        name='libfuzzer_msan_chrome_variant', environment_string=('')).put()
    Job(
        name='afl_asan_chrome_variant', environment_string=('')).put()'''

    self.testcase = test_utils.create_generic_testcase()

  def test_no_minimized_arguments(self):
    """Test that None is returned when minimized arguments is not set."""
    self.testcase.minimized_arguments = ''
    self.testcase.job_id = 'linux_asan_chrome'
    JobApi.get_job = mock.MagicMock()
    JobApi.get_job.return_value = Job(
        name='linux_asan_chrome',
        environment_string=('APP_ARGS = --orig-arg1 --orig-arg2'),
        platform='Linux',
        project_id=uuid4())

    self.assertEqual(
        None,
        setup._get_application_arguments(self.testcase, 'linux_asan_chrome',
                                         'minimize'))
    self.assertEqual(
        None,
        setup._get_application_arguments(
            self.testcase, 'linux_msan_chrome_variant', 'variant'))

  def test_minimized_arguments_for_non_variant_task(self):
    """Test that minimized arguments are returned for non-variant tasks."""
    self.testcase.minimized_arguments = '--orig-arg2'
    JobApi.get_job = mock.MagicMock()
    JobApi.get_job.return_value = Job(
        name='linux_asan_chrome',
        environment_string=('APP_ARGS = --orig-arg1 --orig-arg2'),
        platform='Linux',
        project_id=uuid4())

    self.assertEqual(
        '--orig-arg2',
        setup._get_application_arguments(self.testcase, 'linux_asan_chrome',
                                         'minimize'))

  def test_no_unique_minimized_arguments_for_variant_task(self):
    """Test that only APP_ARGS is returned if minimized arguments have no
    unique arguments, for variant task."""
    self.testcase.minimized_arguments = '--arg2'
    self.testcase.job_id = 'linux_asan_chrome'
    JobApi.get_job = mock.MagicMock()
    JobApi.get_job.return_value = Job(
        name='linux_asan_chrome',
        environment_string=('APP_ARGS = --arg1 --arg2 --arg3="--flag1 --flag2"'),
        platform='Linux',
        project_id=uuid4())

    self.assertEqual(
        '--arg1 --arg2 --arg3="--flag1 --flag2"',
        setup._get_application_arguments(
            self.testcase, 'linux_msan_chrome_variant', 'variant'))

  def test_some_duplicate_minimized_arguments_for_variant_task(self):
    """Test that both minimized arguments and APP_ARGS are returned with
    duplicate args stripped from minimized arguments for variant task."""
    self.testcase.minimized_arguments = '--arg3="--flag1 --flag2" --arg4'
    self.testcase.job_id = 'linux_asan_chrome'
    JobApi.get_job = mock.MagicMock()
    JobApi.get_job.return_value = Job(
        name='linux_asan_chrome',
        environment_string=('APP_ARGS = --arg4 --arg1 --arg2 --arg3="--flag1 --flag2"'),
        platform='Linux',
        project_id=uuid4())

    self.assertEqual(
        '--arg4 --arg1 --arg2 --arg3="--flag1 --flag2"',
        setup._get_application_arguments(
            self.testcase, 'linux_msan_chrome_variant', 'variant'))

  def test_unique_minimized_arguments_for_variant_task(self):
    """Test that both minimized arguments and APP_ARGS are returned when they
    don't have common args for variant task."""
    self.testcase.minimized_arguments = '--arg5'
    self.testcase.job_id = 'linux_asan_chrome'
    JobApi.get_job = mock.MagicMock()
    JobApi.get_job.return_value = Job(
        name='linux_asan_chrome',
        environment_string=('APP_ARGS = --arg5 --arg1 --arg2 --arg3="--flag1 --flag2"'),
        platform='Linux',
        project_id=uuid4())

    self.assertEqual(
        '--arg5 --arg1 --arg2 --arg3="--flag1 --flag2"',
        setup._get_application_arguments(
            self.testcase, 'linux_msan_chrome_variant', 'variant'))

  def test_no_job_app_args_for_variant_task(self):
    """Test that only minimized arguments is returned when APP_ARGS is not set
    in job definition."""
    self.testcase.minimized_arguments = '--arg5'
    self.testcase.job_id = 'libfuzzer_asan_chrome'
    JobApi.get_job = mock.MagicMock()
    JobApi.get_job.return_value = Job(
        name='linux_asan_chrome',
        environment_string=(''),
        platform='Linux',
        project_id=uuid4())

    self.assertEqual(
        '--arg5',
        setup._get_application_arguments(
            self.testcase, 'libfuzzer_msan_chrome_variant', 'variant'))

  def test_afl_job_for_variant_task(self):
    """Test that we use a different argument list if this is an afl variant
    task."""
    self.testcase.minimized_arguments = '--arg5'
    self.testcase.job_id = 'libfuzzer_asan_chrome'
    JobApi.get_job = mock.MagicMock()
    JobApi.get_job.return_value = Job(
        name='linux_asan_chrome',
        environment_string=(''),
        platform='Linux',
        project_id=uuid4())
    
    self.assertEqual(
        '%TESTCASE%',
        setup._get_application_arguments(self.testcase,
                                         'afl_asan_chrome_variant', 'variant'))


# pylint: disable=protected-access
class ClearOldDataBundlesIfNeededTest(fake_filesystem_unittest.TestCase):
  """Tests _clear_old_data_bundles_if_needed."""

  def setUp(self):
    test_utils.set_up_pyfakefs(self)
    test_helpers.patch_environ(self)

    self.data_bundles_dir = '/data-bundles'
    os.mkdir(self.data_bundles_dir)
    environment.set_value('DATA_BUNDLES_DIR', self.data_bundles_dir)

  def test_evict(self):
    """Tests that eviction works when more than certain number of bundles."""
    for i in range(1, 15):
      os.mkdir(os.path.join(self.data_bundles_dir, str(i)))

    setup._clear_old_data_bundles_if_needed()
    self.assertEqual([str(i) for i in range(5, 15)],
                     sorted(os.listdir(self.data_bundles_dir), key=int))

  def test_no_evict(self):
    """Tests that no eviction is required when less than certain number of
    bundles."""
    for i in range(1, 5):
      os.mkdir(os.path.join(self.data_bundles_dir, str(i)))

    setup._clear_old_data_bundles_if_needed()
    self.assertEqual([str(i) for i in range(1, 5)],
                     sorted(os.listdir(self.data_bundles_dir), key=int))


class TestcaseSetupTest(fake_filesystem_unittest.TestCase):
  def setUp(self):
    self.setUpPyfakefs()
    self.data_bundles_dir = os.path.join('/', 'tmp', 'data_bundles')
    if not os.path.exists(self.data_bundles_dir):
      os.makedirs(self.data_bundles_dir)
    
    self.fuzzer = Fuzzer(
      id=uuid4(),
      name='Test Fuzzer',
      builtin=False,
      timestamp=datetime.datetime.now()
    )
    
    self.testcase = Testcase(
      job_id=uuid4(),
      fuzzer_id=self.fuzzer.id,
      absolute_path='/working_directory/test_input/file1',
      timestamp=datetime.datetime.now()
    )
    
    test_helpers.patch_environ(self)
    test_helpers.patch(self, [
        'pingu_sdk.datastore.pingu_api.fuzzer_api.FuzzerApi.get_fuzzer_by_id',
        'pingu_sdk.datastore.pingu_api.fuzzer_api.FuzzerApi.update_fuzzer',
        'pingu_sdk.system.shell.clear_testcase_directories',
        'bot.tasks.setup.update_fuzzer_and_data_bundles'
        
    ])
    
    self.mock.get_fuzzer_by_id.return_value = self.fuzzer
    self.mock.update_fuzzer_and_data_bundles.return_value = True
    
    os.environ['FUZZ_INPUTS'] = 'test_input'
    os.environ['FUZZ_INPUTS_DISK'] = 'test_output_disk'
    os.environ['ROOT_DIR'] = 'working_directory'
    os.environ['JOB_NAME'] = 'job_name'
    os.environ['TEST_TIMEOUT'] = '10'
    
    self.fs.create_dir('working_directory')
    self.fs.create_dir('working_directory/test_input')
    self.fs.create_dir('working_directory/test_output_disk')
    self.fs.create_file('working_directory/test_input/file1', contents='{"key": "value"}')

  def test_setup_test(self):
    result = setup.setup_testcase(testcase=self.testcase, job_id=self.testcase.job_id, fuzzer_override=None)

        