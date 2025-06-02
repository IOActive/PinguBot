
"""Tests for regression_task."""
# pylint: disable=unused-argument
# pylint: disable=protected-access

import datetime
import os
import unittest
from uuid import uuid4

from pingu_sdk.system import errors
from bot.tasks import regression_task
from pingu_sdk.datastore import data_handler
from tests.test_libs import helpers
from tests.test_libs import test_utils
from pingu_sdk.datastore.models import Testcase, Crash


class WriteToBigQueryTest(unittest.TestCase):
  """Test write_to_big_query."""

  def setUp(self):
    helpers.patch(self, [
        #'bot.google_cloud_utils.big_query.write_range',
    ])

    self.testcase = Testcase(
        crash_type='type',
        crash_state='state',
        security_flag=True,
        fuzzer_name='libFuzzer',
        overridden_fuzzer_name='libfuzzer_pdf',
        job_id=uuid4())

class TestcaseReproducesInRevisionTest(unittest.TestCase):
  """Test _testcase_reproduces_in_revision."""

  def setUp(self):
    helpers.patch(self, [
        'pingu_sdk.build_management.build_helper.BuildHelper.setup_regular_build',
        'pingu_sdk.testcase_manager.test_for_crash_with_retries',
        'pingu_sdk.testcase_manager.check_for_bad_build',
    ])

  def test_error_on_failed_setup(self):
    """Ensure that we throw an exception if we fail to set up a build."""
    os.environ['APP_NAME'] = 'app_name'
    # No need to implement a fake setup_regular_build. Since it's doing nothing,
    # we won't have the build directory properly set.
    with self.assertRaises(errors.BuildSetupError):
      regression_task._testcase_reproduces_in_revision(
          None, '/tmp/blah', 'job_type', 1, should_log=False, crash=None)


class TestFoundRegressionNearExtremeRevisions(unittest.TestCase):
  """Test found_regression_near_extreme_revisions."""

  def setUp(self):
    helpers.patch(self, [
        'bot.tasks.regression_task.save_regression_range',
        'bot.tasks.regression_task._testcase_reproduces_in_revision',
    ])

    # Keep a dummy test case. Values are not important, but we need an id.
    self.testcase = Testcase(job_id=uuid4(), fuzzer_id=uuid4(), timestamp=datetime.datetime.now())
    self.crash = Crash(testcase_id=self.testcase.id)

    self.revision_list = [1, 2, 5, 8, 9, 12, 15, 19, 21, 22]

  def test_near_max_revision(self):
    """Ensure that we return True if this is a very recent regression."""

    def testcase_reproduces(testcase,
                            testcase_file_path,
                            job_type,
                            revision,
                            should_log=True,
                            min_revision=None,
                            max_revision=None,
                            crash=None):
      return revision > 20

    self.mock._testcase_reproduces_in_revision.side_effect = testcase_reproduces

    regression_task.found_regression_near_extreme_revisions(
        self.testcase, '/a/b', 'job_name', self.revision_list, 0, 9, crash=self.crash)

  def test_at_min_revision(self):
    """Ensure that we return True if we reproduce in min revision."""
    self.mock._testcase_reproduces_in_revision.return_value = True

    regression_task.found_regression_near_extreme_revisions(
        self.testcase, '/a/b', 'job_name', self.revision_list, 0, 9, crash=self.crash)

  def test_not_at_extreme_revision(self):
    """Ensure that we return False if we didn't regress near an extreme."""

    def testcase_reproduces(testcase,
                            testcase_file_path,
                            job_type,
                            revision,
                            should_log=True,
                            min_revision=None,
                            max_revision=None,
                            crash=None):
      return revision > 10

    self.mock._testcase_reproduces_in_revision.side_effect = testcase_reproduces

    regression_task.found_regression_near_extreme_revisions(
        self.testcase, '/a/b', 'job_name', self.revision_list, 0, 9, crash=self.crash)


def _sample(input_list, count):
  """Helper function to deterministically sample a list."""
  assert count <= len(input_list)
  return input_list[:count]



class ValidateRegressionRangeTest(unittest.TestCase):
  """Tests for validate_regression_range."""

  def setUp(self):
    helpers.patch(self, [
        'bot.tasks.regression_task._testcase_reproduces_in_revision',
        'random.sample',
        'pingu_sdk.datastore.pingu_api.testcase_api.TestcaseApi.get_testcase_by_id'
    ])

    self.mock.sample.side_effect = _sample

  def test_no_earlier_revisions(self):
    """Make sure we don't throw exceptions if nothing is before min revision."""
    testcase = Testcase(job_id=uuid4(), fuzzer_id=uuid4(), timestamp=datetime.datetime.now())
    crash = Crash(testcase_id=testcase.id)

    self.mock._testcase_reproduces_in_revision.return_value = False
    result = regression_task.validate_regression_range(testcase=testcase, testcase_file_path='/a/b',
                                                       job_id='job_type', revision_list=[0], min_index=0, crash=crash)
    self.assertTrue(result)

  def test_one_earlier_revision(self):
    """Test a corner-case with few revisions earlier than min revision."""
    testcase = Testcase(job_id=uuid4(), fuzzer_id=uuid4(), timestamp=datetime.datetime.now())
    crash = Crash(testcase_id=testcase.id)
    
    self.mock._testcase_reproduces_in_revision.return_value = False
    result = regression_task.validate_regression_range(testcase, '/a/b',
                                                       'job_type', [0, 1, 2], 1, crash=crash)
    self.assertTrue(result)

  def test_invalid_range(self):
    """Ensure that we handle invalid ranges correctly."""
    testcase = Testcase(job_id=uuid4(), fuzzer_id=uuid4(), timestamp=datetime.datetime.now())
    crash = Crash(testcase_id=testcase.id)
    self.mock.get_testcase_by_id.return_value = testcase
    
    self.mock._testcase_reproduces_in_revision.return_value = True
    result = regression_task.validate_regression_range(
        testcase, '/a/b', 'job_type', [0, 1, 2, 3, 4], 4, crash=crash)
    self.assertFalse(result)

    #testcase = data_handler.get_testcase_by_id(testcase.id)
    #self.assertEqual(testcase.regression, 'NA')

  def test_valid_range(self):
    """Ensure that we handle valid ranges correctly."""
    testcase = Testcase(job_id=uuid4(), fuzzer_id=uuid4(), timestamp=datetime.datetime.now())
    crash = Crash(testcase_id=testcase.id)
    

    self.mock._testcase_reproduces_in_revision.return_value = False
    result = regression_task.validate_regression_range(
        testcase, '/a/b', 'job_type', [0, 1, 2, 3, 4], 4, crash)
    self.assertTrue(result)
