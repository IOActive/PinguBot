
"""Symbolize task.
   Add stack traces from non-optimized release and debug builds."""

import base64
import os

from pingu_sdk import testcase_manager
from pingu_sdk.crash_analysis import crash_analyzer
from pingu_sdk.crash_analysis.crash_result import CrashResult
from pingu_sdk.datastore import data_handler
from pingu_sdk.metrics import logs
from pingu_sdk.system import environment, tasks, process_handler
from bot.tasks import setup, task_creation
from pingu_sdk.utils import utils
from pingu_sdk.build_management.build_managers import build_utils
from pingu_sdk.datastore.data_constants import TaskState
from pingu_sdk.build_management.build_helper import BuildHelper
from pingu_sdk.datastore.models import Testcase
from pingu_sdk.datastore.pingu_api.pingu_api_client import get_api_client

from bot.tasks.task_context import TaskContext

DEFAULT_REDZONE = 128
MAX_REDZONE = 1024
MIN_REDZONE = 16
STACK_FRAME_COUNT = 128


def execute_task(context: TaskContext):
    testcase_id= context.task.argument
    """Execute a symbolize command."""
    # Locate the testcase associated with the id.
    api_client = get_api_client()
    testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)

    # We should atleast have a symbolized debug or release build.
    if not build_utils.has_symbolized_builds():
        return

    data_handler.update_testcase_comment(testcase, TaskState.STARTED)

    # Setup testcase and its dependencies.
    file_list, _, testcase_file_path = setup.setup_testcase(testcase, context.job.id)
    if not file_list:
        return

    # Initialize variables.
    build_fail_wait = environment.get_value('FAIL_WAIT')

    crash = api_client.crash_api.get_crash_by_testcase(testcase_id=testcase.id)
    old_crash_stacktrace = data_handler.get_stacktrace(crash)
    sym_crash_type = crash.crash_type
    sym_crash_address = crash.crash_address
    sym_crash_state = crash.crash_state
    sym_redzone = DEFAULT_REDZONE
    warmup_timeout = environment.get_value('WARMUP_TIMEOUT')

    # Decide which build revision to use.
    if crash.crash_stacktrace == 'Pending':
        # This usually happen when someone clicked the 'Update stacktrace from
        # trunk' button on the testcase details page. In this case, we are forced
        # to use trunk. No revision -> trunk build.
        build_revision = None
    else:
        build_revision = crash.crash_revision

    # Set up a custom or regular build based on revision.
    build_helper = BuildHelper(job_id=context.job.id, revision=build_revision)
    build_helper.setup_build()

    # Get crash revision used in setting up build.
    crash_revision = environment.get_value('APP_REVISION')

    if not build_utils.check_app_path():
        testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
        data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                             'Build setup failed')
        tasks.add_task(
            'symbolize', testcase_id, context.job.id, wait_time=build_fail_wait)
        return

    # ASAN tool settings (if the tool is used).
    # See if we can get better stacks with higher redzone sizes.
    # A UAF might actually turn out to be OOB read/write with a bigger redzone.
    if environment.tool_matches('ASAN', context.job.id) and crash.security_flag:
        redzone = MAX_REDZONE
        while redzone >= MIN_REDZONE:
            environment.reset_current_memory_tool_options(
                redzone_size=testcase.redzone, disable_ubsan=testcase.disable_ubsan)

            process_handler.terminate_stale_application_instances()
            command = testcase_manager.get_command_line_for_application(
                file_to_run=testcase_file_path)
            return_code, crash_time, output = (
                process_handler.run_process(
                    command, timeout=warmup_timeout, gestures=crash.gestures))
            crash_result = CrashResult(return_code, crash_time, output)

            if crash_result.is_crash() and 'AddressSanitizer' in output:
                state = crash_result.get_symbolized_data()
                security_flag = crash_result.is_security_issue()

                if (not crash_analyzer.ignore_stacktrace(state.crash_stacktrace) and
                        security_flag == crash.security_flag and
                        state.crash_type == crash.crash_type and
                        (state.crash_type != sym_crash_type or
                         state.crash_state != sym_crash_state)):
                    logs.log('Changing crash parameters.\nOld : %s, %s, %s' %
                             (sym_crash_type, sym_crash_address, sym_crash_state))

                    sym_crash_type = state.crash_type
                    sym_crash_address = state.crash_address
                    sym_crash_state = state.crash_state
                    sym_redzone = redzone
                    old_crash_stacktrace = state.crash_stacktrace

                    logs.log('\nNew : %s, %s, %s' % (sym_crash_type, sym_crash_address,
                                                     sym_crash_state))
                    break

            redzone /= 2

    # We should have atleast a symbolized debug or a release build.
    symbolized_builds = build_helper.setup_symbolized_builds(crash_revision)
    if (not symbolized_builds or
            (not build_utils.check_app_path() and
             not build_utils.check_app_path('APP_PATH_DEBUG'))):
        testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
        data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                             'Build setup failed')
        tasks.add_task(
            'symbolize', testcase_id, context.job.id, wait_time=build_fail_wait)
        return

    # Increase malloc_context_size to get all stack frames. Default is 30.
    environment.reset_current_memory_tool_options(
        redzone_size=sym_redzone,
        malloc_context_size=STACK_FRAME_COUNT,
        symbolize_inline_frames=True,
        disable_ubsan=testcase.disable_ubsan)

    # TSAN tool settings (if the tool is used).
    if environment.tool_matches('TSAN', context.job.id):
        environment.set_tsan_max_history_size()

    # Do the symbolization if supported by this application.
    result, sym_crash_stacktrace = (
        get_symbolized_stacktraces(testcase_file_path, testcase,
                                   old_crash_stacktrace, sym_crash_state))

    # Update crash parameters.
    testcase = api_client.testcase_api.get_testcase_by_id(testcase_id)
    crash = api_client.crash_api.get_crash_by_testcase(testcase_id=testcase.id)
    crash.crash_type = sym_crash_type
    crash.crash_address = sym_crash_address
    crash.crash_state = sym_crash_state
    crash.crash_stacktrace = base64.b64encode(
        data_handler.filter_stacktrace(sym_crash_stacktrace)
    .encode()).decode()

    if not result:
        data_handler.update_testcase_comment(
            testcase, TaskState.ERROR,
            'Unable to reproduce crash, skipping '
            'stacktrace update')
    else:
        # Switch build url to use the less-optimized symbolized build with better
        # stacktrace.
        build_url = environment.get_value('BUILD_URL')
        if build_url:
            testcase.set_metadata('build_url', build_url, update_testcase=False)

        data_handler.update_testcase_comment(testcase,
                                             TaskState.FINISHED)

    #crash.symbolized = True
    crash.crash_revision = crash_revision
    api_client.crash_api.update_crash(crash=crash)
    
    # We might have updated the crash state. See if we need to marked as duplicate
    # based on other testcases.
    data_handler.handle_duplicate_entry(testcase)

    #task_creation.create_blame_task_if_needed(testcase)

    # Switch current directory before builds cleanup.
    root_directory = environment.get_value('ROOT_DIR')
    os.chdir(root_directory)

    # Cleanup symbolized builds which are space-heavy.
    symbolized_builds.delete()


def get_symbolized_stacktraces(testcase_file_path, testcase: Testcase,
                               old_crash_stacktrace, expected_state):
    """Use the symbolized builds to generate an updated stacktrace."""
    # Initialize variables.
    app_path = environment.get_value('APP_PATH')
    app_path_debug = environment.get_value('APP_PATH_DEBUG')
    long_test_timeout = environment.get_value('WARMUP_TIMEOUT')
    retry_limit = environment.get_value('FAIL_RETRIES')
    symbolized = False

    debug_build_stacktrace = ''
    release_build_stacktrace = old_crash_stacktrace
    
    crash = get_api_client().crash_api.get_crash_by_testcase(testcase_id=testcase.id)

    # Symbolize using the debug build first so that the debug build stacktrace
    # comes after the more important release build stacktrace.
    if app_path_debug:
        for _ in range(retry_limit):
            process_handler.terminate_stale_application_instances()
            command = testcase_manager.get_command_line_for_application(
                testcase_file_path,
                app_path=app_path_debug,
            )
            return_code, crash_time, output = (
                process_handler.run_process(
                    command, timeout=long_test_timeout, gestures=crash.gestures))
            crash_result = CrashResult(return_code, crash_time, output)

            if crash_result.is_crash():
                state = crash_result.get_symbolized_data()

                if crash_analyzer.ignore_stacktrace(state.crash_stacktrace):
                    continue

                unsymbolized_crash_stacktrace = crash_result.get_stacktrace(
                    symbolized=False)
                debug_build_stacktrace = utils.get_crash_stacktrace_output(
                    command,
                    state.crash_stacktrace,
                    unsymbolized_crash_stacktrace,
                    build_type='debug')
                symbolized = True
                break

    # Symbolize using the release build.
    if app_path:
        for _ in range(retry_limit):
            process_handler.terminate_stale_application_instances()
            command = testcase_manager.get_command_line_for_application(
                testcase_file_path, app_path=app_path)
            return_code, crash_time, output = (
                process_handler.run_process(
                    command, timeout=long_test_timeout, gestures=crash.gestures))
            crash_result = CrashResult(return_code, crash_time, output)

            if crash_result.is_crash():
                state = crash_result.get_symbolized_data()

                if crash_analyzer.ignore_stacktrace(state.crash_stacktrace):
                    continue

                if state.crash_state != expected_state:
                    continue

                # Release stack's security flag has to match the symbolized release
                # stack's security flag.
                security_flag = crash_result.is_security_issue()
                if security_flag != crash.security_flag:
                    continue

                unsymbolized_crash_stacktrace = crash_result.get_stacktrace(
                    symbolized=False)
                release_build_stacktrace = utils.get_crash_stacktrace_output(
                    command,
                    state.crash_stacktrace,
                    unsymbolized_crash_stacktrace,
                    build_type='release')
                symbolized = True
                break

    stacktrace = release_build_stacktrace
    if debug_build_stacktrace:
        stacktrace += '\n\n' + debug_build_stacktrace

    return symbolized, stacktrace
