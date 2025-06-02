
"""Analyze task for handling user uploads."""

import base64
import datetime
from uuid import UUID

import six

from pingu_sdk import testcase_manager
from pingu_sdk.build_management import revisions
from pingu_sdk.build_management.build_helper import BuildHelper
from pingu_sdk.build_management.build_managers import build_utils
from pingu_sdk.crash_analysis import crash_analyzer, severity_analyzer
from pingu_sdk.datastore import data_handler, crash_uploader
from pingu_sdk.datastore.models import Testcase, Crash
from pingu_sdk.fuzzers import engine_common
from pingu_sdk.fuzzing import leak_blacklist
from pingu_sdk.metrics import logs
from pingu_sdk.system import environment, errors, tasks
from bot.tasks import setup, task_creation
from pingu_sdk.utils import utils
from pingu_sdk.datastore.pingu_api.pingu_api_client import get_api_client
from pingu_sdk.datastore.data_constants import TaskState
from pingu_sdk.datastore.pingu_api.storage.build_api import BuildType

from bot.tasks.task_context import TaskContext


def _add_default_issue_metadata(testcase: Testcase):
    """Adds the default issue metadata (e.g. components, labels) to testcase."""
    default_metadata = engine_common.get_all_issue_metadata_for_testcase(testcase)
    if not default_metadata:
        return

    testcase_metadata = testcase.get_metadata()
    for key, default_value in six.iteritems(default_metadata):
        # Add the default issue metadata first. This gives preference to uploader
        # specified issue metadata.
        new_value_list = utils.parse_delimited(
            default_value, delimiter=',', strip=True, remove_empty=True)

        # Append uploader specified testcase metadata value to end (for preference).
        uploader_value = testcase_metadata.get(key, '')
        uploader_value_list = utils.parse_delimited(
            uploader_value, delimiter=',', strip=True, remove_empty=True)
        for value in uploader_value_list:
            if value not in new_value_list:
                new_value_list.append(value)

        new_value = ','.join(new_value_list)
        if new_value == uploader_value:
            continue

        logs.log('Updating issue metadata for {} from {} to {}.'.format(
            key, uploader_value, new_value))
        testcase.set_metadata(key, new_value)


def setup_build(testcase: Testcase, crash: Crash, job_id: UUID, project_id: UUID):
    """Set up a custom or regular build based on revision. For regular builds,
  if a provided revision is not found, set up a build with the
  closest revision <= provided revision."""

    revision = crash.crash_revision

    if revision and not build_utils.is_custom_binary():
        revision_list = build_utils.get_revisions_list(project_id=project_id, build_type=BuildType.RELEASE, testcase=testcase)
        if not revision_list:
            logs.log_error('Failed to fetch revision list.')
            return

        revision_index = revisions.find_min_revision_index(revision_list, revision)
        if revision_index is None:
            raise errors.BuildNotFoundError(revision, testcase.job_type)
        revision = revision_list[revision_index]

    build_helper = BuildHelper(job_id=job_id, revision=revision)
    return build_helper.setup_build()


def execute_task(context: TaskContext):
    """Run analyze task."""
    testcase_id = context.task.argument
    # Reset redzones.
    environment.reset_current_memory_tool_options(redzone_size=128)

    # Unset window location size and position properties so as to use default.
    environment.set_value('WINDOW_ARG', '')

    # Locate the testcase associated with the id.
    api_client = get_api_client()
    testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
    crash = api_client.crash_api.get_crash_by_testcase(str(testcase.id))
    if not testcase and not crash:
        return

    data_handler.update_testcase_comment(testcase, TaskState.STARTED)

    is_lsan_enabled = environment.get_value('LSAN')
    if is_lsan_enabled:
        # Creates empty local blacklist so all leaks will be visible to uploader.
        leak_blacklist.create_empty_local_blacklist()

    # Adjust the test timeout, if user has provided one.
    if testcase.timeout:
        environment.set_value('TEST_TIMEOUT', testcase.timeout)

    # Adjust the number of retries, if user has provided one.
    if testcase.retries is not None:
        environment.set_value('CRASH_RETRIES', testcase.retries)

    # Set up testcase and get absolute testcase path.
    file_list, _, testcase_file_path = setup.setup_testcase(testcase, context.job.id)
    if not file_list:
        return

    # Set up build.
    build_setup_result = setup_build(job_id=context.job.id, testcase=testcase, crash=crash, project_id=context.project.id)

    # Check if we have an application path. If not, our build failed
    # to setup correctly.
    if not build_setup_result and not build_utils.check_app_path():
        data_handler.update_testcase_comment(testcase, TaskState.ERROR, 'Build setup failed\n')

        if data_handler.is_first_retry_for_task(testcase):
            build_fail_wait = environment.get_value('FAIL_WAIT')
            tasks.add_task(
                'analyze', testcase_id, context.job.id, wait_time=build_fail_wait)
        else:
            data_handler.close_invalid_uploaded_testcase(testcase, testcase.get_metadata(),
                                                         'Build setup failed')
        return

    # Update initial testcase information.
    testcase.absolute_path = testcase_file_path
    testcase.job_id = context.job.id
    #testcase.binary_flag = utils.is_binary_file(testcase_file_path)
    testcase.queue = tasks.default_queue()
    crash.crash_state = ''

    # Set initial testcase metadata fields (e.g. build url, etc).
    data_handler.set_initial_testcase_metadata(testcase)

    # Update minimized arguments and use ones provided during user upload.
    if not testcase.minimized_arguments:
        minimized_arguments = environment.get_value('APP_ARGS') or ''
        additional_command_line_flags = testcase.get_metadata(
            'uploaded_additional_args')
        if additional_command_line_flags:
            minimized_arguments += ' %s' % additional_command_line_flags
        environment.set_value('APP_ARGS', minimized_arguments)
        testcase.minimized_arguments = minimized_arguments

    # Update other fields not set at upload time.

    crash.crash_revision = environment.get_value('APP_REVISION')
    data_handler.set_initial_testcase_metadata(testcase)
    api_client.testcase_api.update_testcase(testcase=testcase)

    # Initialize some variables.
    gestures = crash.gestures
    test_timeout = environment.get_value('TEST_TIMEOUT')

    # Get the crash output.
    result = testcase_manager.test_for_crash_with_retries(
        testcase,
        testcase_file_path,
        test_timeout,
        crash,
        compare_crash=False)

    # Refresh our object.
    testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
    if not testcase:
        return

    # Set application command line with the correct http flag.
    application_command_line = (
        testcase_manager.get_command_line_for_application(
            testcase_file_path, needs_http=False))

    # Get the crash data.
    crashed = result.is_crash()
    crash_time = result.get_crash_time()
    state = result.get_symbolized_data()
    unsymbolized_crash_stacktrace = base64.b64encode(
            result.get_stacktrace(symbolized=False)
        .encode()).decode()
    # Get crash info object with minidump info. Also, re-generate unsymbolized
    # stacktrace if needed.
    crash_info, _ = (
        crash_uploader.get_crash_info_and_stacktrace(
            application_command_line, state.crash_stacktrace, gestures))
    if crash_info:
        testcase.minidump_keys = crash_info.store_minidump()

    if not crashed:
        # Could not reproduce the crash.
        log_message = (
                'Testcase didn\'t crash in %d seconds (with retries)\n' % test_timeout)
        data_handler.update_testcase_comment(
            testcase, TaskState.FINISHED, log_message)

        # In the general case, we will not attempt to symbolize if we do not detect
        # a crash. For user uploads, we should symbolize anyway to provide more
        # information about what might be happening.
        crash_stacktrace_output = utils.get_crash_stacktrace_output(
            application_command_line, state.crash_stacktrace,
            unsymbolized_crash_stacktrace)

        crash.crash_stacktrace = base64.b64encode(
            data_handler.filter_stacktrace(crash_stacktrace_output)
        .encode()).decode()
        
        # For an unreproducible testcase, retry once on another bot to confirm
        # our results and in case this bot is in a bad state which we didn't catch
        # through our usual means.
        if data_handler.is_first_retry_for_task(testcase):
            testcase.status = 'unreproducible'
            api_client.crash_api.update_crash(testcase)

            tasks.add_task('analyze', testcase_id, context.job.id)
            return

        data_handler.close_invalid_uploaded_testcase(testcase,
                                                     'Unreproducible')

        # A non-reproducing testcase might still impact production branches.
        # Add the impact task to get that information.
        task_creation.create_impact_task_if_needed(testcase)
        return

    # Update testcase crash parameters.
    crash.crash_type = state.crash_type
    crash.crash_address = state.crash_address
    crash.crash_state = state.crash_state
    crash_stacktrace_output = utils.get_crash_stacktrace_output(
        application_command_line, state.crash_stacktrace,
        unsymbolized_crash_stacktrace)
    
    crash.crash_stacktrace = base64.b64encode(
        data_handler.filter_stacktrace(crash_stacktrace_output)
    .encode()).decode()

    crash.unsymbolized_crash_stacktrace = unsymbolized_crash_stacktrace

    # Try to guess if the bug is security or not.
    security_flag = crash_analyzer.is_security_issue(
        state.crash_stacktrace, state.crash_type, state.crash_address)
    crash.security_flag = security_flag

    # If it is, guess the severity.
    if security_flag:
        crash.security_severity = severity_analyzer.get_security_severity(
            state.crash_type, state.crash_stacktrace, context.job.name, bool(gestures))

    log_message = ('Testcase crashed in %d seconds (r%d) \n' %
                   (crash_time, crash.crash_revision))
    data_handler.update_testcase_comment(testcase, TaskState.FINISHED,
                                         log_message)

    # See if we have to ignore this crash.
    if crash_analyzer.ignore_stacktrace(state.crash_stacktrace):
        data_handler.close_invalid_uploaded_testcase(testcase,
                                                     'Irrelavant')
        return

    # Test for reproducibility.
    fuzz_target = api_client.fuzz_target_api.get_fuzz_target_by_keyName(testcase.fuzzer_id, environment.get_value("FUZZ_TARGET"))
    one_time_crasher_flag = not testcase_manager.test_for_reproducibility(
        fuzzer_name=testcase.fuzzer_id,
        fuzztarget_id=fuzz_target.id,
        testcase_path=testcase_file_path,
        expected_state=state.crash_state,
        expected_security_flag=security_flag,
        test_timeout=test_timeout, 
        http_flag=False, 
        gestures=gestures,
        arguments=environment.get_value('APP_ARGS') or '')
    
    testcase.one_time_crasher_flag = one_time_crasher_flag

    # Check to see if this is a duplicate.
    data_handler.check_uploaded_testcase_duplicate(testcase, crash)

    # Set testcase and metadata status if not set already.
    if testcase.status == 'duplicate':
        # For testcase uploaded by bots (with quiet flag), don't create additional
        # tasks.
        if testcase.quiet_flag:
            data_handler.close_invalid_uploaded_testcase(testcase,
                                                         'Duplicate')
            return
    else:
        # New testcase.
        testcase.status = 'processed'
        #metadata.status = 'Confirmed'

        # Reset the timestamp as well, to respect
        # data_types.MIN_ELAPSED_TIME_SINCE_REPORT. Otherwise it may get filed by
        # triage task prematurely without the grouper having a chance to run on this
        # testcase.
        testcase.timestamp = utils.utcnow()

        # Add new leaks to global blacklist to avoid detecting duplicates.
        # Only add if testcase has a direct leak crash and if it's reproducible.
        if is_lsan_enabled:
            leak_blacklist.add_crash_to_global_blacklist_if_needed(testcase)

    # Update the testcase values.
    api_client.testcase_api.update_testcase(testcase=testcase)

    # Update the upload metadata.
    crash.security_flag = security_flag
    api_client.crash_api.update_crash(crash=crash)

    _add_default_issue_metadata(testcase)

    # Create tasks to
    # 1. Minimize testcase (minimize).
    # 2. Find regression range (regression).
    # 3. Find testcase impact on production branches (impact).
    # 4. Check whether testcase is fixed (progression).
    # 5. Get second stacktrace from another job in case of
    #    one-time crashes (stack).
    task_creation.create_tasks(testcase)
