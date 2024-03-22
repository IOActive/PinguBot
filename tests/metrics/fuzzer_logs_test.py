
"""fuzzer_logs test."""
import datetime
import unittest

import mock

from bot.metrics import fuzzer_logs
from bot.system import environment
from bot.tests.test_libs import helpers as test_helpers


class FuzzerLogsTest(unittest.TestCase):
  """Tests for logs uploading."""

  def setUp(self):
    test_helpers.patch_environ(self)
    environment.set_value('FUZZER_NAME', 'fuzzer_1')
    environment.set_value('JOB_NAME', 'fake_job')

    # To be used for generation of date and time when uploading a log.
    self.fake_utcnow = datetime.datetime(2017, 3, 21, 11, 15, 13, 666666)
    self.fake_log_time = datetime.datetime(2017, 4, 22, 12, 16, 14, 777777)

    test_helpers.patch(self, [
        'datetime.datetime',
        'bot.google_cloud_utils.storage.write_data',
    ])

    self.mock.datetime.utcnow.return_value = self.fake_utcnow

  def test_upload_to_logs(self):
    """Test a simple call to upload_to_logs."""
    mock_gsutil = mock.MagicMock()
    self.mock.write_data.return_value = mock_gsutil
    fuzzer_logs.upload_to_logs('fake-gcs-bucket', 'fake content')
    self.mock.write_data.assert_called_once_with(
        'fake content',
        'gs://fake-gcs-bucket/fuzzer_1/fake_job/2017-03-21/11:15:13:666666.log')

  def test_upload_to_logs_with_all_arguments(self):
    """Test a call to upload_to_logs with all arguments being passed."""
    mock_gsutil = mock.MagicMock()
    self.mock.write_data.return_value = mock_gsutil
    fuzzer_logs.upload_to_logs(
        'gcs-bucket',
        'fake content',
        time=self.fake_log_time,
        fuzzer_name='fuzzer_2',
        job_type='another_job')
    self.mock.write_data.assert_called_once_with(
        'fake content',
        'gs://gcs-bucket/fuzzer_2/another_job/2017-04-22/12:16:14:777777.log')