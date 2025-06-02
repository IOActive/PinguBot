
"""Tests for corpus_pruning_task."""
# pylint: disable=unused-argument
# pylint: disable=protected-access

import datetime
import os
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock
from uuid import uuid4

from mock import patch
import mock
import six

from pingu_sdk.fuzzers import options
from pingu_sdk.fuzzers.libFuzzer import \
    engine as libFuzzer_engine
from bot.tasks import corpus_pruning_task

from bot.tasks.task_context import TaskContext
from tests.test_libs import helpers
from tests.test_libs import test_utils
from pingu_sdk.datastore.models import FuzzTarget, FuzzTargetJob, Job, Testcase, Fuzzer

TEST_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), 'corpus_pruning_task_data')

TEST_GLOBAL_BUCKET = 'test-global-bundle'
TEST_SHARED_BUCKET = 'test-shared-corpus'
TEST2_BACKUP_BUCKET = 'test2-backup-bucket'


class BaseTest(object):
  """Base corpus pruning tests."""

  def setUp(self):
    """Setup."""
    helpers.patch_environ(self)
    helpers.patch(self, [
        'pingu_sdk.fuzzers.engine_common.unpack_seed_corpus_if_needed',
        'bot.tasks.corpus_pruning_task.choose_cross_pollination_strategy',
        'bot.tasks.task_creation.create_tasks',
        'bot.tasks.setup.update_fuzzer_and_data_bundles',
        'pingu_sdk.fuzzing.corpus_manager.backup_corpus',
        'pingu_sdk.fuzzing.corpus_manager.FuzzTargetCorpus.rsync_to_disk',
        'pingu_sdk.fuzzing.corpus_manager.FuzzTargetCorpus.rsync_from_disk',
        'pingu_sdk.datastore.blobs_manager.write_blob',
        'pingu_sdk.datastore.storage.write_data',
        'pingu_sdk.fuzzers.engine.Engine.get',
        'pingu_sdk.datastore.pingu_api.fuzzer_api.FuzzerApi.get_fuzzer',
        'pingu_sdk.system.archive.unpack',

    ])
    self.corpus_storage_rsync_to_disk = patch(
        'pingu_sdk.fuzzing.corpus_manager.CorpusStorage.rsync_to_disk',
        side_effect=lambda directory: self._mock_rsync_to_disk2(directory)
    ).start()
    
    self.mock.unpack.return_value = True
    self.mock.get.return_value = libFuzzer_engine.Engine()
    self.mock.rsync_to_disk.side_effect = self._mock_rsync_to_disk
    self.mock.rsync_from_disk.side_effect = self._mock_rsync_from_disk
    self.mock.update_fuzzer_and_data_bundles.return_value = True
    self.mock.write_blob.return_value = 'key'
    self.mock.backup_corpus.return_value = 'backup_link'
    self.mock.choose_cross_pollination_strategy.return_value = ('random', None)

    def mocked_unpack_seed_corpus_if_needed(*args, **kwargs):
      """Mock's assert called methods are not powerful enough to ensure that
      unpack_seed_corpus_if_needed was called once with force_unpack=True.
      Instead, just assert that it was called once and during the call assert
      that it was called correctly.
      """
      self.assertTrue(kwargs.get('force_unpack', False))

    self.mock.unpack_seed_corpus_if_needed.side_effect = (
        mocked_unpack_seed_corpus_if_needed)
    
    project_id = uuid4()
    self.job = Job(platform='Linux', project_id=project_id)
    
    self.fuzzer  = Fuzzer(name='fantasy_fuzz', filename="", file_size="1", blobstore_path="",
                    executable_path="fantasy_fuzz",
                    timeout=10, supported_platforms="Linux", launcher_script="", max_testcases=10,
                    additional_environment_string="", builtin=False, differential=False,
                    untrusted_content=False)
    
    self.mock.get_fuzzer.return_value = self.fuzzer
    
    self.fuzz_target = FuzzTarget(fuzzer_id=self.fuzzer.id, binary='test_fuzzer', project_id=project_id)
    
    self.fuzz_target_job = FuzzTargetJob(
        fuzz_target_id=self.fuzz_target.id,
        fuzzer_id=self.fuzzer.id,
        job_id=self.job.id)
    
    self.testcase = Testcase(job_id=self.job.id, fuzzer_id=self.fuzzer.id, timestamp=datetime.datetime.now())

    self.fuzz_inputs_disk = tempfile.mkdtemp()
    self.bot_tmpdir = tempfile.mkdtemp()
    self.build_dir = os.path.join(TEST_DIR, 'build')
    self.corpus_bucket = tempfile.mkdtemp()
    self.corpus_dir = os.path.join(self.corpus_bucket, 'corpus')
    self.quarantine_dir = os.path.join(self.corpus_bucket, 'quarantine')
    self.shared_corpus_dir = os.path.join(self.corpus_bucket, 'shared')

    shutil.copytree(os.path.join(TEST_DIR, 'corpus'), self.corpus_dir)
    shutil.copytree(os.path.join(TEST_DIR, 'quarantine'), self.quarantine_dir)
    shutil.copytree(os.path.join(TEST_DIR, 'shared'), self.shared_corpus_dir)

    os.environ['BOT_TMPDIR'] = self.bot_tmpdir
    os.environ['FUZZ_INPUTS'] = self.fuzz_inputs_disk
    os.environ['FUZZ_INPUTS_DISK'] = self.fuzz_inputs_disk
    os.environ['CORPUS_BUCKET'] = 'bucket'
    os.environ['QUARANTINE_BUCKET'] = 'bucket-quarantine'
    os.environ['SHARED_CORPUS_BUCKET'] = 'bucket-shared'
    os.environ['JOB_NAME'] = 'libfuzzer_asan_job'
    os.environ['FAIL_RETRIES'] = '1'
    os.environ['APP_REVISION'] = '1337'
    os.environ['MINIO_HOST'] = '127.0.0.1:9000'
    os.environ['ACCESS_KEY'] = 'mK6kUOlDZ834q0wL'
    os.environ['SECRET_KEY'] = 'Hq1cuslNaaAFcLXU6q45fqhrFGFG3UCO' 
 
  def tearDown(self):
    shutil.rmtree(self.fuzz_inputs_disk, ignore_errors=True)
    shutil.rmtree(self.bot_tmpdir, ignore_errors=True)
    shutil.rmtree(self.corpus_bucket, ignore_errors=True)

  def _mock_setup_build(self, revision=None):
    os.environ['BUILD_DIR'] = self.build_dir
    return True

  def _mock_rsync_to_disk(self, _, directory):
    """Mock rsync_to_disk."""
    if 'quarantine' in directory:
      corpus_dir = self.quarantine_dir
    elif 'shared' in directory:
      corpus_dir = self.shared_corpus_dir
    else:
      corpus_dir = self.corpus_dir

    if os.path.exists(directory):
      shutil.rmtree(directory, ignore_errors=True)

    shutil.copytree(corpus_dir, directory)
    return True
  
  def _mock_rsync_to_disk2(self, directory):
    self._mock_rsync_to_disk(None, directory=directory)

  def _mock_rsync_from_disk(self, _, directory):
    """Mock rsync_from_disk."""
    if 'quarantine' in directory:
      corpus_dir = self.quarantine_dir
    else:
      corpus_dir = self.corpus_dir

    if os.path.exists(corpus_dir):
      shutil.rmtree(corpus_dir, ignore_errors=True)

    shutil.copytree(directory, corpus_dir)
    return True

  def _mock_add_testcase(self, testcase:Testcase):
    self.testcase = testcase

# TODO(unassigned): Support macOS.
@test_utils.supported_platforms('LINUX')

class CorpusPruningTest(unittest.TestCase, BaseTest):
  """Corpus pruning tests."""

  def setUp(self):
    BaseTest.setUp(self)
    helpers.patch(self, [
        'pingu_sdk.build_management.build_helper.BuildHelper.setup_build',
        'pingu_sdk.system.utils.get_application_id',
        'pingu_sdk.datastore.pingu_api.fuzztarget_api.FuzzTargetApi.get_fuzz_target_by_id',
        'pingu_sdk.datastore.pingu_api.task_api.TaskApi.get_task_status',
        'pingu_sdk.datastore.data_handler.update_task_status',
        'pingu_sdk.datastore.pingu_api.fuzztarget_job_api.FuzzTargetJobApi.get_fuzz_target_jobs_by_engine',
        'pingu_sdk.datastore.pingu_api.job_api.JobApi.get_job',
        'pingu_sdk.datastore.storage.copy_file_from',
        'pingu_sdk.datastore.storage.exists',
        'pingu_sdk.datastore.pingu_api.testcase_api.TestcaseApi.get_testcase_by_id',
        'pingu_sdk.datastore.pingu_api.testcase_api.TestcaseApi.update_testcase',
        'pingu_sdk.datastore.pingu_api.testcase_api.TestcaseApi.add_testcase',
        'pingu_sdk.datastore.pingu_api.testcase_api.TestcaseApi.find_testcase',
        'pingu_sdk.datastore.pingu_api.fuzztarget_api.FuzzTargetApi.get_fuzz_target_by_keyName',
        'pingu_sdk.config.local_config.Config.get',
    ])
    
    self.mock.setup_build.side_effect = self._mock_setup_build
    self.mock.get_application_id.return_value = 'project'
    self.mock.get_fuzz_target_by_id.return_value = self.fuzz_target
    self.mock.get_fuzz_target_jobs_by_engine.return_value = [self.fuzz_target_job]
    self.mock.get_job.return_value = self.job
    self.mock.exists.return_value = True
    self.mock.add_testcase.side_effect = self._mock_add_testcase
    self.mock.get_testcase_by_id.return_value = self.testcase
    self.mock.find_testcase.return_value = self.testcase
    self.mock.get_fuzz_target_by_keyName.return_value = self.fuzz_target
    self.mock.get = "test-bucket"

  def test_prune(self):
    """Basic pruning test."""
    task=mock.MagicMock(command="prune", argument="libFuzzer,test_fuzzer", id=uuid4())
    task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=self.job, fuzzer_name='fuzzer')

    corpus_pruning_task.execute_task(task_context)

    quarantined = os.listdir(self.quarantine_dir)
    self.assertEqual(1, len(quarantined))
    self.assertEqual(quarantined[0], 'crash-7acd6a2b3fe3c5ec97fa37e5a980c106367491fa')

    corpus = os.listdir(self.corpus_dir)
    self.assertEqual(4, len(corpus))
    six.assertCountEqual(self, [
        '39e0574a4abfd646565a3e436c548eeb1684fb57',
        '7d157d7c000ae27db146575c08ce30df893d3a64',
        '31836aeaab22dc49555a97edb4c753881432e01d',
        '6fa8c57336628a7d733f684dc9404fbd09020543',
    ], corpus)

  def test_get_libfuzzer_flags(self):
    """Test get_libfuzzer_flags logic."""
    context = corpus_pruning_task.CorpusPurningContext(
      fuzzer=self.fuzzer,
      fuzz_target=self.fuzz_target, 
      cross_pollinate_fuzzers=[], 
      cross_pollination_method=corpus_pruning_task.Pollination.RANDOM, 
      tag=None)

    runner = corpus_pruning_task.Runner(self.build_dir, context)
    flags = runner.get_libfuzzer_flags()
    expected_default_flags = [
        '-timeout=5', '-rss_limit_mb=2560', '-max_len=5242880',
        '-detect_leaks=1', '-use_value_profile=1'
    ]
    six.assertCountEqual(self, flags, expected_default_flags)

    runner.fuzzer_options = options.FuzzerOptions(
        os.path.join(self.build_dir, 'test_get_libfuzzer_flags.options'))
    flags = runner.get_libfuzzer_flags()
    expected_custom_flags = [
        '-timeout=5', '-rss_limit_mb=2560', '-max_len=5242880', '-detect_leaks=1',
        '-use_value_profile=1'
    ]
    six.assertCountEqual(self, flags, expected_custom_flags)