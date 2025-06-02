
"""commands tests."""
import datetime
import os
import unittest
from uuid import uuid4

import mock

from bot.tasks import commands
from pingu_sdk.system import environment
from bot.tasks.task_context import TaskContext
from tests.test_libs import helpers
from tests.test_libs import test_utils
from pingu_sdk.datastore.data_constants import TaskState

from pingu_sdk.datastore.models.fuzzer import Fuzzer


@commands.set_task_payload
def dummy(_):
  """A dummy function."""
  return os.environ['TASK_PAYLOAD']


@commands.set_task_payload
def dummy_exception(_):
  """A dummy function."""
  raise Exception(os.environ['TASK_PAYLOAD'])


class SetTaskPayloadTest(unittest.TestCase):
  """Test set_task_payload."""

  def setUp(self):
    helpers.patch_environ(self)

  def test_set(self):
    """Test set."""
    task = mock.Mock()
    task.payload.return_value = 'payload something'
    self.assertEqual('payload something', dummy(task))
    self.assertIsNone(os.getenv('TASK_PAYLOAD'))


#@test_utils.with_cloud_emulators('datastore')
class RunCommandTest(unittest.TestCase):
  """Tests for run_command."""

  def setUp(self):
    helpers.patch_environ(self)
    helpers.patch(self, [
        'pingu_sdk.datastore.data_handler.update_task_status',
        'pingu_sdk.utils.utils.utcnow',
        'pingu_sdk.datastore.pingu_api.fuzzer_api.FuzzerApi.get_fuzzer',
    ])

    os.environ['BOT_NAME'] = 'bot_name'
    os.environ['TASK_LEASE_SECONDS'] = '60'
    os.environ['FAIL_WAIT'] = '60'
    self.mock.utcnow.return_value = test_utils.CURRENT_TIME
    self.mock.update_task_status.return_value = True
    
    fuzzer = Fuzzer(name='fantasy_fuzz', filename="", file_size="1", blobstore_path="",
                    executable_path="fantasy_fuzz",
                    timeout=10, supported_platforms="Linux", launcher_script="", max_testcases=10,
                    additional_environment_string="", builtin=False, differential=False,
                    untrusted_content=False)
        
    self.mock.get_fuzzer.return_value = fuzzer
    
  def test_run_command_fuzz(self):
    helpers.patch(self, [
        'bot.tasks.fuzz_task.execute_task',
    ])
    """Test run_command with a normal command."""
    task=mock.MagicMock(command="fuzz", argument="fuzzer", id=uuid4())
    task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=mock.MagicMock(id=uuid4()), fuzzer_name='fuzzer')

    commands.run_command(task_context)

    self.assertEqual(1, self.mock.execute_task.call_count)
    self.mock.execute_task.assert_called_with(task_context)


  def test_run_command_progression(self):
    helpers.patch(self, [
      'bot.tasks.progression_task.execute_task',
    ])
    """Test run_command with a progression task."""
    task=mock.MagicMock(command="progression", argument="1234", id=uuid4())
    task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=mock.MagicMock(id=uuid4()), fuzzer_name='fuzzer')
    commands.run_command(task_context)

    self.assertEqual(1, self.mock.execute_task.call_count)
    self.mock.execute_task.assert_called_with(task_context)

  def test_run_command_exception(self):
    helpers.patch(self, [
      'bot.tasks.progression_task.execute_task',
    ])
    """Test run_command with an exception."""
    self.mock.execute_task.side_effect = Exception

    task=mock.MagicMock(command="progression", argument="1234", id=uuid4())
    task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=mock.MagicMock(id=uuid4()), fuzzer_name='fuzzer')
    
    with self.assertRaises(Exception):
      commands.run_command('progression', '123', 'job')

  def test_run_command_already_running(self):
    helpers.patch(self, [
      'bot.tasks.progression_task.execute_task',
    ])
    self.mock.update_task_status.return_value = False
    """Test run_command with another instance currently running."""
    
    task=mock.MagicMock(command="progression", argument="1234", id=uuid4())
    task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=mock.MagicMock(id=uuid4()), fuzzer_name='fuzzer')

    with self.assertRaises(commands.AlreadyRunningError):
      commands.run_command(task_context)

    self.assertEqual(0, self.mock.execute_task.call_count)

  def test_run_command_already_running_expired(self):
    helpers.patch(self, [
      'bot.tasks.progression_task.execute_task',
    ])
    
    task=mock.MagicMock(command="progression", argument="1234", id=uuid4())
    task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=mock.MagicMock(id=uuid4()), fuzzer_name='fuzzer')
    """Test run_command with another instance currently running, but its lease
    has expired."""
    commands.run_command(task_context)
    self.assertEqual(1, self.mock.execute_task.call_count)

class UpdateEnvironmentForJobTest(unittest.TestCase):
  """update_environment_for_job tests."""

  def setUp(self):
    helpers.patch_environ(self)

  def test_basic(self):
    """Basic tests."""
    commands.update_environment_for_job('FUZZ_TEST_TIMEOUT = 123\n'
                                        'MAX_TESTCASES = 5\n'
                                        'B = abcdef\n')
    self.assertEqual(123, environment.get_value('FUZZ_TEST_TIMEOUT'))
    self.assertEqual(5, environment.get_value('MAX_TESTCASES'))
    self.assertEqual('abcdef', environment.get_value('B'))

  def test_timeout_overrides(self):
    """Test timeout overrides."""
    environment.set_value('FUZZ_TEST_TIMEOUT_OVERRIDE', 9001)
    environment.set_value('MAX_TESTCASES_OVERRIDE', 42)
    commands.update_environment_for_job(
        'FUZZ_TEST_TIMEOUT = 123\nMAX_TESTCASES = 5\n')
    self.assertEqual(9001, environment.get_value('FUZZ_TEST_TIMEOUT'))
    self.assertEqual(42, environment.get_value('MAX_TESTCASES'))
