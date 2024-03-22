
"""Tests for analyze task."""

import unittest

from bot.tasks import analyze_task
from bot.tests.test_libs import helpers
from bot.tests.test_libs import test_utils


@test_utils.with_cloud_emulators('datastore')
class AddDefaultIssueMetadataTest(unittest.TestCase):
  """Test _add_default_issue_metadata."""

  def setUp(self):
    helpers.patch(
        self,
        [
            'bot.bot_working_directory.fuzzers.engine_common.'
            'get_all_issue_metadata_for_testcase',
            # Disable logging.
            'bot.datastore.data_types.Testcase._post_put_hook',
            'bot.metrics.logs.log',
        ])

  def test_union(self):
    """Test union of current testcase metadata and default issue metadata."""
    self.mock.get_all_issue_metadata_for_testcase.return_value = {
        'issue_owners': 'dev1@example1.com, dev2@example2.com',
        'issue_components': 'component1',
        'issue_labels': 'label1, label2 ,label3'
    }

    testcase = test_utils.create_generic_testcase()
    testcase.set_metadata('issue_owners', 'dev3@example3.com,dev2@example2.com')
    testcase.set_metadata('issue_components', 'component2')
    testcase.set_metadata('issue_labels', 'label4,label5, label2,')

    analyze_task._add_default_issue_metadata(testcase)  # pylint: disable=protected-access
    self.assertEqual('dev1@example1.com,dev2@example2.com,dev3@example3.com',
                     testcase.get_metadata('issue_owners'))
    self.assertEqual('component1,component2',
                     testcase.get_metadata('issue_components'))
    self.assertEqual('label1,label2,label3,label4,label5',
                     testcase.get_metadata('issue_labels'))
    self.assertEqual(3, self.mock.log.call_count)

  def test_no_testcase_metadata(self):
    """Test when we only have default issue metadata and no testcase
    metadata."""
    self.mock.get_all_issue_metadata_for_testcase.return_value = None

    testcase = test_utils.create_generic_testcase()
    testcase.set_metadata('issue_owners', 'dev1@example1.com,dev2@example2.com')
    testcase.set_metadata('issue_components', 'component1')
    testcase.set_metadata('issue_labels', 'label1,label2,label3')

    analyze_task._add_default_issue_metadata(testcase)  # pylint: disable=protected-access
    self.assertEqual('dev1@example1.com,dev2@example2.com',
                     testcase.get_metadata('issue_owners'))
    self.assertEqual('component1', testcase.get_metadata('issue_components'))
    self.assertEqual('label1,label2,label3',
                     testcase.get_metadata('issue_labels'))
    self.assertEqual(0, self.mock.log.call_count)

  def test_no_default_issue_metadata(self):
    """Test when we only have testcase metadata and no default issue
    metadata."""
    self.mock.get_all_issue_metadata_for_testcase.return_value = {
        'issue_owners': 'dev1@example1.com,dev2@example2.com',
        'issue_components': 'component1',
        'issue_labels': 'label1,label2,label3'
    }

    testcase = test_utils.create_generic_testcase()

    analyze_task._add_default_issue_metadata(testcase)  # pylint: disable=protected-access
    self.assertEqual('dev1@example1.com,dev2@example2.com',
                     testcase.get_metadata('issue_owners'))
    self.assertEqual('component1', testcase.get_metadata('issue_components'))
    self.assertEqual('label1,label2,label3',
                     testcase.get_metadata('issue_labels'))
    self.assertEqual(3, self.mock.log.call_count)

  def test_same_testcase_and_default_issue_metadata(self):
    """Test when we have same testcase metadata and default issue metadata."""
    self.mock.get_all_issue_metadata_for_testcase.return_value = {
        'issue_owners': 'dev1@example1.com,dev2@example2.com',
        'issue_components': 'component1',
        'issue_labels': 'label1,label2,label3'
    }

    testcase = test_utils.create_generic_testcase()
    testcase.set_metadata('issue_owners', 'dev1@example1.com,dev2@example2.com')
    testcase.set_metadata('issue_components', 'component1')
    testcase.set_metadata('issue_labels', 'label1,label2,label3')

    analyze_task._add_default_issue_metadata(testcase)  # pylint: disable=protected-access
    self.assertEqual('dev1@example1.com,dev2@example2.com',
                     testcase.get_metadata('issue_owners'))
    self.assertEqual('component1', testcase.get_metadata('issue_components'))
    self.assertEqual('label1,label2,label3',
                     testcase.get_metadata('issue_labels'))
    self.assertEqual(0, self.mock.log.call_count)
