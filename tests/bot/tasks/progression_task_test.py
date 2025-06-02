
"""Tests for regression_task."""

import datetime
import json
import os
import unittest
from uuid import uuid4

import mock
from pyfakefs import fake_filesystem_unittest

from pingu_sdk.system import errors
from bot.tasks.progression_task import ProgressionTask
from bot.tasks.task_context import TaskContext
from tests.test_libs import helpers
from tests.test_libs import test_utils
from pingu_sdk.datastore.models import Testcase, FuzzTarget, Crash
from pingu_sdk.datastore.models.fuzzer import Fuzzer

class TestcaseReproducesInRevisionTest(unittest.TestCase):
  """Test _testcase_reproduces_in_revision."""

  def setUp(self):
    helpers.patch(self, [
        'pingu_sdk.build_management.build_helper.BuildHelper.setup_regular_build',
        'pingu_sdk.testcase_manager.test_for_crash_with_retries',
        'pingu_sdk.testcase_manager.check_for_bad_build',
        'pingu_sdk.datastore.pingu_api.fuzzer_api.FuzzerApi.get_fuzzer',

    ])
    
    fuzzer = Fuzzer(name='fantasy_fuzz', filename="", file_size="1", blobstore_path="",
                executable_path="fantasy_fuzz",
                timeout=10, supported_platforms="Linux", launcher_script="", max_testcases=10,
                additional_environment_string="", builtin=False, differential=False,
                untrusted_content=False)
        
    self.mock.get_fuzzer.return_value = fuzzer
    
    task=mock.MagicMock(command="fuzz", argument="fuzzer", id=uuid4())
    task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=mock.MagicMock(id=uuid4()), fuzzer_name='fuzzer')
    
    self.progression_task = ProgressionTask(task_context)

  def test_error_on_failed_setup(self):
    """Ensure that we throw an exception if we fail to set up a build."""
    os.environ['APP_NAME'] = 'app_name'
    # No need to implement a fake setup_regular_build. Since it's doing nothing,
    # we won't have the build directory properly set.
    with self.assertRaises(errors.BuildSetupError):
      self.progression_task._testcase_reproduces_in_revision(  # pylint: disable=protected-access
          testcase=None, testcase_file_path='/tmp/blah', job_type='job_type', revision=1, crash=None)


class UpdateIssueMetadataTest(unittest.TestCase):
  """Test _update_issue_metadata."""

  def setUp(self):
    helpers.patch(self, [
        'pingu_sdk.fuzzers.engine_common.find_fuzzer_path',
        'pingu_sdk.fuzzers.engine_common.get_all_issue_metadata',
        'pingu_sdk.datastore.models.testcase.Testcase.get_fuzz_target',
        'pingu_sdk.datastore.pingu_api.fuzzer_api.FuzzerApi.get_fuzzer',

    ])
    self.fuzzer_id = uuid4()
    self.job_id = uuid4()
    self.project_id = uuid4()
    self.fuzztarget = FuzzTarget(project_id=self.project_id , binary='fuzzer', fuzzer_id=self.fuzzer_id)
    self.mock.get_all_issue_metadata.return_value = {
        'issue_labels': 'label1',
        'issue_components': 'component1',
    }

    self.testcase = Testcase(
        overridden_fuzzer_name='libFuzzer_fuzzer', job_id=self.job_id, fuzzer_id=self.fuzzer_id, timestamp=datetime.datetime.now())
    self.crash = Crash(testcase_id=self.testcase.id)
    self.mock.find_fuzzer_path.return_value = '/tmp/blah'
    self.mock.get_fuzz_target.return_value = self.fuzztarget
    
    fuzzer = Fuzzer(name='fantasy_fuzz', filename="", file_size="1", blobstore_path="",
                executable_path="fantasy_fuzz",
                timeout=10, supported_platforms="Linux", launcher_script="", max_testcases=10,
                additional_environment_string="", builtin=False, differential=False,
                untrusted_content=False)
        
    self.mock.get_fuzzer.return_value = fuzzer
    
    task=mock.MagicMock(command="fuzz", argument="fuzzer", id=uuid4())
    task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=mock.MagicMock(id=uuid4()), fuzzer_name='fuzzer')
    
    self.progression_task = ProgressionTask(task_context)

  def test_update_issue_metadata_non_existent(self):
    """Test update issue metadata a testcase with no metadata."""
    self.progression_task._update_issue_metadata(self.testcase)  # pylint: disable=protected-access

    testcase = self.testcase
    self.assertDictEqual({
        'issue_labels': 'label1',
        'issue_components': 'component1',
    }, json.loads(testcase.additional_metadata))

  def test_update_issue_metadata_replace(self):
    """Test update issue metadata a testcase with different metadata."""
    self.testcase.additional_metadata = json.dumps({
        'issue_labels': 'label1',
        'issue_components': 'component2',
    })
    self.progression_task._update_issue_metadata(self.testcase)  # pylint: disable=protected-access

    testcase = self.testcase
    self.assertDictEqual({
        'issue_labels': 'label1',
        'issue_components': 'component1',
    }, json.loads(testcase.additional_metadata))

  def test_update_issue_metadata_same(self):
    """Test update issue metadata a testcase with the same metadata."""
    self.testcase.additional_metadata = json.dumps({
        'issue_labels': 'label1',
        'issue_components': 'component1',
    })

    self.crash.crash_type = 'test'  # Should not be written.
    self.progression_task._update_issue_metadata(self.testcase)  # pylint: disable=protected-access

    testcase = self.testcase
    self.assertDictEqual({
        'issue_labels': 'label1',
        'issue_components': 'component1',
    }, json.loads(testcase.additional_metadata))
    #self.assertIsNone(self.crash.crash_type)


class StoreTestcaseForRegressionTesting(fake_filesystem_unittest.TestCase):
  """Test _store_testcase_for_regression_testing."""

  def setUp(self):
    test_utils.set_up_pyfakefs(self)
    helpers.patch_environ(self)
    helpers.patch(self, [
        'pingu_sdk.fuzzing.corpus_manager.CorpusStorage.upload_files',
        'pingu_sdk.datastore.pingu_api.fuzztarget_api.FuzzTargetApi.get_fuzz_target_by_id',
        'pingu_sdk.config.local_config.Config.get',
        'pingu_sdk.datastore.pingu_api.fuzzer_api.FuzzerApi.get_fuzzer',

    ])

    os.environ['CORPUS_BUCKET'] = 'corpus'
    os.environ['MINIO_HOST'] = 'minio.io'
    os.environ['MINIO_ACCESS_KEY'] = 'access'
    os.environ['MINIO_SECRET_KEY'] = 'secret'
    self.fuzzer_id = uuid4()
    self.project_id = uuid4()
    self.fuzz_target = FuzzTarget(binary='/test_fuzzer', project_id=self.project_id, fuzzer_id=self.fuzzer_id)

    self.testcase = Testcase(job_id=uuid4(), fuzzer_id=self.fuzzer_id, timestamp=datetime.datetime.now())
    self.testcase.bug_information = '123'
    self.testcase.open = False

    self.testcase_file_path = '/testcase'
    self.fs.create_file(self.testcase_file_path, contents='A')
    self.mock.get_fuzz_target_by_id.return_value = self.fuzz_target
    self.mock.get.return_value = 'corpus'
    
    fuzzer = Fuzzer(name='fantasy_fuzz', filename="", file_size="1", blobstore_path="",
                executable_path="fantasy_fuzz",
                timeout=10, supported_platforms="Linux", launcher_script="", max_testcases=10,
                additional_environment_string="", builtin=False, differential=False,
                untrusted_content=False)
        
    self.mock.get_fuzzer.return_value = fuzzer
    
    task=mock.MagicMock(command="fuzz", argument="fuzzer", id=uuid4())
    task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=mock.MagicMock(id=uuid4()), fuzzer_name='fuzzer')
    
    self.progression_task = ProgressionTask(task_context)

  def test_open_testcase(self):
    """Test that an open testcase is not stored for regression testing."""
    self.testcase.open = True

    self.progression_task._store_testcase_for_regression_testing(  # pylint: disable=protected-access
        self.testcase, self.testcase_file_path)
    self.assertEqual(0, self.mock.upload_files.call_count)

  def test_testcase_with_no_issue(self):
    """Test that a testcase with no associated issue is not stored for
    regression testing."""
    self.testcase.bug_information = ''

    self.progression_task._store_testcase_for_regression_testing(  # pylint: disable=protected-access
        self.testcase, self.testcase_file_path)
    self.assertEqual(0, self.mock.upload_files.call_count)

  def test_testcase_with_no_fuzz_target(self):
    """Test that a testcase with no associated fuzz target is not stored for
    regression testing."""
    self.mock.get_fuzz_target_by_id.return_value = None
    self.progression_task._store_testcase_for_regression_testing(  # pylint: disable=protected-access
        self.testcase, self.testcase_file_path)
    self.assertEqual(0, self.mock.upload_files.call_count)

  def test_testcase_stored(self):
    """Test that a testcase is stored for regression testing."""
    self.progression_task._store_testcase_for_regression_testing(self.testcase, self.testcase_file_path)
    self.mock.upload_files.assert_called_with(
        mock.ANY,
        ['/testcase'])
