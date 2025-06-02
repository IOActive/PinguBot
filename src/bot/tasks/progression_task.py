"""Test to see if test cases are fixed."""

import os
import time
from typing import cast

import six

from pingu_sdk import testcase_manager
from pingu_sdk.build_management import revisions
from pingu_sdk.build_management.build_managers import build_utils
from pingu_sdk.build_management.build_helper import BuildHelper
from pingu_sdk.datastore.data_constants import TaskState
from pingu_sdk.datastore import data_handler, crash_uploader
from pingu_sdk.fuzzers import engine_common
from pingu_sdk.fuzzing import corpus_manager
from pingu_sdk.metrics import logs
from pingu_sdk.system import environment, tasks, errors
from bot.tasks import setup, task_creation
from pingu_sdk.utils import utils
from pingu_sdk.crash_analysis.crash_result import CrashResult
from pingu_sdk.datastore.models import Testcase, Crash
from pingu_sdk.datastore.pingu_api.pingu_api_client import get_api_client

from bot.tasks.task_context import TaskContext
from pingu_sdk.datastore.pingu_api.storage.build_api import BuildType


class ProgressionTask:
    def __init__(self, context: TaskContext):
        self.context = context

    def _log_output(self, revision, crash_result: CrashResult):
        """Log process output."""
        logs.log(
            'Testing %s.' % revision,
            revision=revision,
            output=crash_result.get_stacktrace(symbolized=True))

    def _check_fixed_for_custom_binary(self, testcase: Testcase, job_id, testcase_file_path):
        """Simplified fixed check for test cases using custom binaries."""
        revision = environment.get_value('APP_REVISION')

        # Update comments to reflect bot information and clean up old comments.
        testcase_id = testcase.id()
        api_client = get_api_client()
        testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
        crash = api_client.crash_api.get_crash_by_testcase(str(testcase.id))
        data_handler.update_testcase_comment(testcase, TaskState.STARTED)
        build_helper = BuildHelper(job_id=job_id)
        build_helper.setup_build()
        if not build_utils.check_app_path():
            testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
            data_handler.update_testcase_comment(
                testcase, TaskState.ERROR,
                'Build setup failed for custom binary')
            build_fail_wait = environment.get_value('FAIL_WAIT')
            tasks.add_task(
                'progression', testcase_id, job_id, wait_time=build_fail_wait)
            return

        test_timeout = environment.get_value('TEST_TIMEOUT', 10)
        result = testcase_manager.test_for_crash_with_retries(
            testcase, testcase_file_path, test_timeout, crash)
        self._log_output(revision, result)

        # Re-fetch to finalize testcase updates in branches below.
        testcase = api_client.testcase_api.get_testcase_by_id(testcase.id)

        # If this still crashes on the most recent build, it's not fixed. The task
        # will be rescheduled by a cron job and re-attempted eventually.
        if result.is_crash():
            app_path = environment.get_value('APP_PATH')
            command = testcase_manager.get_command_line_for_application(
                testcase_file_path, app_path=app_path)
            symbolized_crash_stacktrace = result.get_stacktrace(symbolized=True)
            unsymbolized_crash_stacktrace = result.get_stacktrace(symbolized=False)
            stacktrace = utils.get_crash_stacktrace_output(
                command, symbolized_crash_stacktrace, unsymbolized_crash_stacktrace)
            #testcase.last_tested_crash_stacktrace = data_handler.filter_stacktrace(stacktrace)
            data_handler.update_progression_completion_metadata(
                testcase,
                revision,
                is_crash=True,
                message='still crashes on latest custom build')
            return

        if result.unexpected_crash:
            testcase.set_metadata(
                'crashes_on_unexpected_state', True, update_testcase=False)
        else:
            testcase.delete_metadata(
                'crashes_on_unexpected_state', update_testcase=False)

        # Retry once on another bot to confirm our results and in case this bot is in
        # a bad state which we didn't catch through our usual means.
        if data_handler.is_first_retry_for_task(testcase, reset_after_retry=True):
            tasks.add_task('progression', testcase_id, job_id)
            data_handler.update_progression_completion_metadata(testcase, revision)
            return

        # The bug is fixed.
        testcase.fixed = 'Yes'
        testcase.open = False
        data_handler.update_progression_completion_metadata(
            testcase, revision, message='fixed on latest custom build')

    def _update_issue_metadata(self, testcase: Testcase):
        """Update issue metadata."""
        metadata = engine_common.get_all_issue_metadata_for_testcase(testcase)
        if not metadata:
            return

        for key, value in six.iteritems(metadata):
            old_value = testcase.get_metadata(key)
            if old_value != value:
                logs.log('Updating issue metadata for {} from {} to {}.'.format(
                    key, old_value, value))
                testcase.set_metadata(key, value)

    def _testcase_reproduces_in_revision(self,
                                         job_id,
                                         testcase: Testcase,
                                         testcase_file_path,
                                         job_type,
                                         revision,
                                         crash: Crash,
                                         update_metadata=False) -> CrashResult:
        """Test to see if a test case reproduces in the specified revision."""
        build_helper = BuildHelper(job_id=job_id, revision=revision)
        build_helper.setup_build()
        if not build_utils.check_app_path():
            raise errors.BuildSetupError(revision, job_type)

        if testcase_manager.check_for_bad_build(job_type, revision):
            log_message = 'Bad build at r%d. Skipping' % revision
            testcase = get_api_client().testcase_api.get_testcase_by_id(testcase.id)
            data_handler.update_testcase_comment(testcase, TaskState.WIP,
                                                 log_message)
            raise errors.BadBuildError(revision, job_type)

        test_timeout = environment.get_value('TEST_TIMEOUT', 10)
        result = testcase_manager.test_for_crash_with_retries(
            testcase, testcase_file_path, test_timeout, crash=crash)
        self._log_output(revision, result)

        if update_metadata:
            self._update_issue_metadata(testcase)

        return result

    def _save_current_fixed_range_indices(self, testcase_id, fixed_range_start,
                                          fixed_range_end):
        """Save current fixed range indices in case we die in middle of task."""
        api_client = get_api_client()
        testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
        testcase.set_metadata(
            'last_progression_min', fixed_range_start, update_testcase=False)
        testcase.set_metadata(
            'last_progression_max', fixed_range_end, update_testcase=False)
        api_client.testcase_api.update_testcase(testcase)

    def _save_fixed_range(self, testcase_id, min_revision, max_revision,
                          testcase_file_path):
        """Update a test case and other metadata with a fixed range."""
        testcase = get_api_client().testcase_api.get_testcase_by_id(testcase_id)
        testcase.fixed = '%d:%d' % (min_revision, max_revision)
        testcase.open = False

        data_handler.update_progression_completion_metadata(
            testcase, max_revision, message='fixed in range r%s' % testcase.fixed)

        self._store_testcase_for_regression_testing(testcase, testcase_file_path)

    def _store_testcase_for_regression_testing(self, testcase: Testcase, testcase_file_path):
        """Stores reproduction testcase for future regression testing in corpus
      pruning task."""
        if testcase.open:
            # Store testcase only after the crash is fixed.
            return

        if not testcase.bug_information:
            # Only store crashes with bugs associated with them.
            return
        api_client = get_api_client()
        fuzz_target = api_client.fuzz_target_api.get_fuzz_target_by_id(testcase.fuzzer_id)
        if not fuzz_target:
            # No work to do, only applicable for engine fuzzers.
            return

        corpus = corpus_manager.FuzzTargetCorpus(self.context.fuzzer.id, fuzz_target.id)
        
        try:
            corpus.upload_files([testcase_file_path])
        except Exception as e:
            logs.log_error('Failed to store testcase for regression testing')

    def find_fixed_range(self):
        """Attempt to find the revision range where a testcase was fixed."""
        deadline = tasks.get_task_completion_deadline()
        api_client = get_api_client()
        testcase_id = self.context.task.argument
        testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
        crash = api_client.crash_api.get_crash_by_testcase(str(testcase.id))
        if not testcase:
            return

        if testcase.fixed:
            logs.log_error('Fixed range is already set as %s, skip.' % testcase.fixed)
            return

        # Setup testcase and its dependencies.
        file_list, _, testcase_file_path = setup.setup_testcase(testcase, self.context.job.id)
        if not file_list:
            return

        # Set a flag to indicate we are running progression task. This shows pending
        # status on testcase report page and avoid conflicting testcase updates by
        # triage cron.
        testcase.set_metadata('progression_pending', True)

        # Custom binaries are handled as special cases.
        if build_utils.is_custom_binary():
            self._check_fixed_for_custom_binary(testcase, self.context.job.id, testcase_file_path)
            return

        revision_list = build_utils.get_revisions_list(project_id=self.context.project.id, build_type=BuildType.RELEASE.value.value, testcase=testcase)

        if not revision_list:
            data_handler.close_testcase_with_error(testcase_id,
                                                   'Failed to fetch revision list')
            return

        # Use min, max_index to mark the start and end of revision list that is used
        # for bisecting the progression range. Set start to the revision where noticed
        # the crash. Set end to the trunk revision. Also, use min, max from past run
        # if it timed out.
        min_revision = testcase.get_metadata('last_progression_min')
        max_revision = testcase.get_metadata('last_progression_max')

        if min_revision or max_revision:
            # Clear these to avoid using them in next run. If this run fails, then we
            # should try next run without them to see it succeeds. If this run succeeds,
            # we should still clear them to avoid capping max revision in next run.
            testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
            testcase.delete_metadata('last_progression_min', update_testcase=False)
            testcase.delete_metadata('last_progression_max', update_testcase=False)
            api_client.testcase_api.update_testcase(testcase)

        last_tested_revision = testcase.get_metadata('last_tested_crash_revision')
        known_crash_revision = last_tested_revision or crash.crash_revision
        if not min_revision:
            min_revision = known_crash_revision
        if not max_revision:
            max_revision = revisions.get_last_revision_in_list(revision_list)

        min_index = revisions.find_min_revision_index(revision_list, min_revision)
        if min_index is None:
            raise errors.BuildNotFoundError(min_revision, self.context.job.id)
        max_index = revisions.find_max_revision_index(revision_list, max_revision)
        if max_index is None:
            raise errors.BuildNotFoundError(max_revision, self.context.job.id)

        testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
        data_handler.update_testcase_comment(testcase, TaskState.STARTED,
                                             'r%d' % max_revision)

        # Check to see if this testcase is still crashing now. If it is, then just
        # bail out.
        result = cast(CrashResult, self._testcase_reproduces_in_revision(
            self.context.job.id,
            testcase,
            testcase_file_path,
            self.context.job.id,
            max_revision,
            update_metadata=True))
        
        if result.is_crash():
            logs.log('Found crash with same signature on latest revision r%d.' %
                     max_revision)
            app_path = environment.get_value('APP_PATH')
            command = testcase_manager.get_command_line_for_application(
                testcase_file_path, app_path=app_path)
            symbolized_crash_stacktrace = result.get_stacktrace(symbolized=True)
            unsymbolized_crash_stacktrace = result.get_stacktrace(symbolized=False)
            stacktrace = utils.get_crash_stacktrace_output(
                command, symbolized_crash_stacktrace, unsymbolized_crash_stacktrace)
            testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
            #testcase.last_tested_crash_stacktrace = data_handler.filter_stacktrace(stacktrace)
            data_handler.update_progression_completion_metadata(
                testcase,
                max_revision,
                is_crash=True,
                message='still crashes on latest revision r%s' % max_revision)

            # Since we've verified that the test case is still crashing, clear out any
            # metadata indicating potential flake from previous runs.
            task_creation.mark_unreproducible_if_flaky(testcase, False)

            # For chromium project, save latest crash information for later upload
            # to chromecrash/.
            state = result.get_symbolized_data()
            crash_uploader.save_crash_info_if_needed(testcase_id, max_revision,
                                                     self.context.job.id, state.crash_type,
                                                     state.crash_address, state.frames)
            return

        if result.unexpected_crash:
            testcase.set_metadata('crashes_on_unexpected_state', True)
        else:
            testcase.delete_metadata('crashes_on_unexpected_state')

        # Don't burden NFS server with caching these random builds.
        environment.set_value('CACHE_STORE', False)

        # Verify that we do crash in the min revision. This is assumed to be true
        # while we are doing the bisect.
        result = self._testcase_reproduces_in_revision(testcase, testcase_file_path,
                                                  self.context.job.id, min_revision, crash=crash)
        if result and not result.is_crash():
            testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)

            # Retry once on another bot to confirm our result.
            if data_handler.is_first_retry_for_task(testcase, reset_after_retry=True):
                tasks.add_task('progression', testcase_id, self.context.job.id)
                error_message = (
                        'Known crash revision %d did not crash, will retry on another bot to '
                        'confirm result' % known_crash_revision)
                data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                                     error_message)
                data_handler.update_progression_completion_metadata(
                    testcase, max_revision)
                return

            data_handler.clear_progression_pending(testcase)
            error_message = (
                    'Known crash revision %d did not crash' % known_crash_revision)
            data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                                 error_message)
            task_creation.mark_unreproducible_if_flaky(testcase, True)
            return

        # Start a binary search to find last non-crashing revision. At this point, we
        # know that we do crash in the min_revision, and do not crash in max_revision.
        while time.time() < deadline:
            min_revision = revision_list[min_index]
            max_revision = revision_list[max_index]

            # If the min and max revisions are one apart this is as much as we can
            # narrow the range.
            if max_index - min_index == 1:
                self._save_fixed_range(testcase_id, min_revision, max_revision,
                                  testcase_file_path)
                return

            # Occasionally, we get into this bad state. It seems to be related to test
            # cases with flaky stacks, but the exact cause is unknown.
            if max_index - min_index < 1:
                testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
                testcase.fixed = 'NA'
                testcase.open = False
                message = ('Fixed testing errored out (min and max revisions '
                           'are both %d)' % min_revision)
                data_handler.update_progression_completion_metadata(
                    testcase, max_revision, message=message)

                # Let the bisection service know about the NA status.
                # bisection.request_bisection(testcase)
                return

            # Test the middle revision of our range.
            middle_index = (min_index + max_index) // 2
            middle_revision = revision_list[middle_index]

            testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
            log_message = 'Testing r%d (current range %d:%d)' % (
                middle_revision, min_revision, max_revision)
            data_handler.update_testcase_comment(testcase, TaskState.WIP,
                                                 log_message)

            try:
                result = self._testcase_reproduces_in_revision(testcase, testcase_file_path,
                                                          self.context.job.id, middle_revision, crash=crash)
            except errors.BadBuildError:
                # Skip this revision.
                del revision_list[middle_index]
                max_index -= 1
                continue

            if result.is_crash():
                min_index = middle_index
            else:
                max_index = middle_index

            self._save_current_fixed_range_indices(testcase_id, revision_list[min_index],
                                              revision_list[max_index])

        # If we've broken out of the loop, we've exceeded the deadline. Recreate the
        # task to pick up where we left off.
        testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
        error_message = ('Timed out, current range r%d:r%d' %
                         (revision_list[min_index], revision_list[max_index]))
        data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                             error_message)
        tasks.add_task('progression', testcase_id, self.context.job.id)


def execute_task(context: TaskContext):
    """Execute progression task."""
    progression_task = ProgressionTask(context)
    try:
        progression_task.find_fixed_range()
    except errors.BuildSetupError as error:
        # If we failed to setup a build, it is likely a bot error. We can retry
        # the task in this case.
        testcase_id = context.task.argument
        testcase = get_api_client().testcase_api.get_testcase_by_id(testcase_id)
        error_message = 'Build setup failed r%d' % error.revision
        data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                             error_message)
        build_fail_wait = environment.get_value('FAIL_WAIT')
        tasks.add_task(
            'progression', testcase_id, context.job.id, wait_time=build_fail_wait)
    except errors.BadBuildError:
        # Though bad builds when narrowing the range are recoverable, certain builds
        # being marked as bad may be unrecoverable. Recoverable ones should not
        # reach this point.
        testcase = get_api_client().testcase_api.get_testcase_by_id(testcase_id)
        error_message = 'Unable to recover from bad build'
        data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                             error_message)
