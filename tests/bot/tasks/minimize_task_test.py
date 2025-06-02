
"""Tests for corpus_pruning_task."""
import base64
import datetime
import os
import shutil
import tempfile
import unittest
from uuid import uuid4

# pylint: disable=unused-argument
import mock

from pingu_sdk.utils import utils
from pingu_sdk.fuzzers import init as fuzzers_init
from bot.tasks import minimize_task
from pingu_sdk.datastore import data_handler
from pingu_sdk.system import environment
from bot.tasks.task_context import TaskContext
from tests.test_libs import helpers
from tests.test_libs import test_utils
from pingu_sdk.datastore.models import Job, Testcase, FuzzTarget, FuzzTargetJob, Fuzzer, Crash

TEST_DIR = os.path.join(
    os.path.dirname(os.path.realpath(__file__)), 'minimize_task_data')


class LibFuzzerMinimizeTaskTest(unittest.TestCase):
  """libFuzzer Minimize task tests."""

  def setUp(self):
    helpers.patch_environ(self)
    helpers.patch(self, [
        'bot.tasks.minimize_task._run_libfuzzer_testcase',
        'bot.tasks.minimize_task._run_libfuzzer_tool',
        'pingu_sdk.datastore.pingu_api.job_api.JobApi.get_job',
        'pingu_sdk.datastore.pingu_api.task_api.TaskApi.add_task',
        'pingu_sdk.datastore.pingu_api.testcase_api.TestcaseApi.get_testcase_by_id',
        'pingu_sdk.datastore.pingu_api.fuzzer_api.FuzzerApi.get_fuzzer',
    ])

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
    
    fuzzer = Fuzzer(name='fantasy_fuzz', filename="", file_size="1", blobstore_path="",
                executable_path="fantasy_fuzz",
                timeout=10, supported_platforms="Linux", launcher_script="", max_testcases=10,
                additional_environment_string="", builtin=False, differential=False,
                untrusted_content=False)
        
    self.mock.get_fuzzer.return_value = fuzzer
    
    task=mock.MagicMock(command="fuzz", argument="fuzzer", id=uuid4())
    self.task_context = TaskContext(task=task, project=mock.MagicMock(id=uuid4()), job=mock.MagicMock(id=uuid4()), fuzzer_name='fuzzer')
    
    

  def test_libfuzzer_skip_minimization_initial_crash_state(self):
    """Test libFuzzer minimization skipping with a valid initial crash state."""
    # TODO(ochang): Fix circular import.
    from pingu_sdk.crash_analysis.crash_result import CrashResult

    self.job = Job(name='libfuzzer_asan_job', platform='Linux', project_id=uuid4())
    self.testcase = Testcase(
        minimized_keys='',
        fuzzed_keys='FUZZED_KEY',
        job_type='libfuzzer_asan_job',
        security_flag=True,
        timestamp=datetime.datetime.now(),
        job_id=self.job.id,
        fuzzer_id=uuid4()
    )
    self.crash = Crash(testcase_id=self.testcase.id)
    self.mock.get_job.return_value = self.job
    self.mock.get_testcase_by_id.return_value = self.testcase
    
    stacktrace = (
        '==14970==ERROR: AddressSanitizer: heap-buffer-overflow on address '
        '0x61b00001f7d0 at pc 0x00000064801b bp 0x7ffce478dbd0 sp '
        '0x7ffce478dbc8 READ of size 4 at 0x61b00001f7d0 thread T0\n'
        '#0 0x64801a in frame0() src/test.cpp:1819:15\n'
        '#1 0x647ac5 in frame1() src/test.cpp:1954:25\n'
        '#2 0xb1dee7 in frame2() src/test.cpp:160:9\n'
        '#3 0xb1ddd8 in frame3() src/test.cpp:148:34\n')
    
    self.crash.crash_stacktrace = stacktrace
    self.crash.crash_address = '0x61b00001f7d0'
    self.crash.crash_state = 'frame0\nframe1\nframe2\n'
    self.crash.crash_type = 'Heap-buffer-overflow'
    self.crash.security_flag = True
    
    self.mock._run_libfuzzer_testcase.return_value = CrashResult(1, 1.0, stacktrace)

    self.mock._run_libfuzzer_tool.return_value = (None, None)

    minimize_task.do_libfuzzer_minimization(testcase=self.testcase, testcase_file_path='/testcase_file_path', crash=self.crash, project_id=self.task_context.project.id)

    self.assertEqual('Heap-buffer-overflow', self.crash.crash_type)
    self.assertEqual('frame0\nframe1\nframe2\n', self.crash.crash_state)
    self.assertEqual('0x61b00001f7d0', self.crash.crash_address)
    self.assertEqual(
        '+----------------------------------------Release Build Stacktrace'
        '----------------------------------------+\n%s' % stacktrace,
        base64.b64decode(self.crash.crash_stacktrace).decode("utf-8"))