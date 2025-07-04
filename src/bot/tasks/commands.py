"""Run command based on the current task."""

import os
import sys
import six

from pingu_sdk.datastore import data_handler
from pingu_sdk.metrics import logs
from pingu_sdk.system import environment, tasks, errors
from pingu_sdk.system import process_handler
from pingu_sdk.system import shell
from bot.tasks import analyze_task
from bot.tasks import corpus_pruning_task
from bot.tasks import fuzz_task
from bot.tasks import minimize_task
from bot.tasks import progression_task
from bot.tasks import regression_task
from bot.tasks import symbolize_task
from bot.tasks.task_context import TaskContext
#from bot.tasks import upload_reports_task
from pingu_sdk.utils import utils
from pingu_sdk.datastore.data_constants import TaskState
from pingu_sdk.datastore.pingu_api.pingu_api_client import get_api_client
from pingu_sdk.system.tasks import Task

COMMAND_MAP = {
    'analyze': analyze_task,
    'corpus_pruning': corpus_pruning_task,
    'fuzz': fuzz_task,
    'minimize': minimize_task,
    'progression': progression_task,
    'regression': regression_task,
    'symbolize': symbolize_task,
    #'upload_reports': upload_reports_task,
}

TASK_RETRY_WAIT_LIMIT = 5 * 60  # 5 minutes.


class Error(Exception):
    """Base commands exceptions."""


class AlreadyRunningError(Error):
    """Exception raised for a task that is already running on another bot."""


def cleanup_task_state():
    """Cleans state before and after a task is executed."""
    # Cleanup stale processes.
    process_handler.cleanup_stale_processes()

    # Clear build urls, temp and testcase directories.
    shell.clear_build_urls_directory()
    shell.clear_crash_stacktraces_directory()
    shell.clear_testcase_directories()
    shell.clear_temp_directory()
    shell.clear_system_temp_directory()
    shell.clear_device_temp_directories()

    # Reset memory tool environment variables.
    environment.reset_current_memory_tool_options()

    # Call python's garbage collector.
    utils.python_gc()


def is_supported_cpu_arch_for_job():
    """Return true if the current cpu architecture can run this job."""
    cpu_arch = environment.get_cpu_arch()
    if not cpu_arch:
        # No cpu architecture check is defined for this platform, bail out.
        return True

    supported_cpu_arch = environment.get_value('CPU_ARCH')
    if not supported_cpu_arch:
        # No specific cpu architecture requirement specified in job, bail out.
        return True

    # Convert to list just in case anyone specifies value as a single string.
    supported_cpu_arch_list = list(supported_cpu_arch)

    return cpu_arch in supported_cpu_arch_list


def update_environment_for_job(environment_string):
    """Process the environment variable string included with a job."""
    # Now parse the job's environment definition.
    environment_values = (
        environment.parse_environment_definition(environment_string))

    for key, value in six.iteritems(environment_values):
        environment.set_value(key, value)

    # If we share the build with another job type, force us to be a custom binary
    # job type.
    if environment.get_value('SHARE_BUILD_WITH_JOB_TYPE'):
        environment.set_value('CUSTOM_BINARY', True)

    # Allow the default FUZZ_TEST_TIMEOUT and MAX_TESTCASES to be overridden on
    # machines that are preempted more often.
    fuzz_test_timeout_override = environment.get_value(
        'FUZZ_TEST_TIMEOUT_OVERRIDE')
    if fuzz_test_timeout_override:
        environment.set_value('FUZZ_TEST_TIMEOUT', fuzz_test_timeout_override)

    max_testcases_override = environment.get_value('MAX_TESTCASES_OVERRIDE')
    if max_testcases_override:
        environment.set_value('MAX_TESTCASES', max_testcases_override)


def set_task_payload(func):
    """Set TASK_PAYLOAD and unset TASK_PAYLOAD."""

    def wrapper(task: Task):
        """Wrapper."""
        environment.set_value('TASK_PAYLOAD', task.payload())
        try:
            return func(task)
        except:  # Truly catch *all* exceptions.
            e = sys.exc_info()[1]
            e.extras = {'task_payload': environment.get_value('TASK_PAYLOAD')}
            if should_update_task_status(environment.get_value('TASK_ID')):
                data_handler.update_task_status(environment.get_value('TASK_ID'),
                                                TaskState.ERROR)
            raise
        finally:
            environment.remove_key('TASK_PAYLOAD')

    return wrapper


def should_update_task_status(task_name):
    """Whether the task status should be automatically handled."""
    return task_name not in [
        # Multiple fuzz tasks are expected to run in parallel.
        #'fuzz',

        # The task payload can't be used as-is for de-duplication purposes as it
        # includes revision. corpus_pruning_task calls update_task_status itself
        # to handle this.
        # TODO(ochang): This will be cleaned up as part of migration to Pub/Sub.
        'corpus_pruning',
    ]


def run_command(context: TaskContext):
    """Run the command."""
    task_name = context.task.command
    task_argument = context.task.argument
    job = context.job

    if task_name not in COMMAND_MAP:
        logs.log_error("Unknown command '%s'" % task_name)
        return

    task_module = COMMAND_MAP[task_name]

    # If applicable, ensure this is the only instance of the task running.
    task_state_name = ' '.join([task_name, task_argument, str(job.id)])
    if should_update_task_status(task_name):
        if not data_handler.update_task_status(context.task.id, TaskState.STARTED):
            logs.log('Another instance of "{}" already '
                     'running, exiting.'.format(task_state_name))
            raise AlreadyRunningError

    try:
        task_module.execute_task(context)
    except errors.InvalidTestcaseError:
        logs.log_warn('Test case %s no longer exists.' % task_argument)
        if should_update_task_status(task_name):
            data_handler.update_task_status(context.task.id, TaskState.ERROR)
    except BaseException as e:
        if should_update_task_status(task_name):
            data_handler.update_task_status(context.task.id, TaskState.ERROR)
        raise
    except Exception as e:
        raise Exception(e)

    if should_update_task_status(task_name):
        data_handler.update_task_status(context.task.id, TaskState.FINISHED)


# pylint: disable=too-many-nested-blocks
@set_task_payload
def process_command(task: Task):
    """Figures out what to do with the given task and executes the command."""
    logs.log("Executing command '%s'" % task.payload())
    if not task.payload().strip():
        logs.log_error('Empty task received.')
        return

    # Parse task payload.
    task_name = task.command
    task_argument = task.argument
    api_client = get_api_client()
    job = api_client.job_api.get_job(task.job)
    if not job:
        logs.log_error("Job not found.")
        return
       
    # Download job related project configuration
    try:
        project = api_client.project_api.get_project_by_id(job.project_id)
        project_config_path = os.path.join(environment.get_value('ROOT_DIR'), 'config', 'project.yaml')
        with open(project_config_path, 'w') as f:
            f.write(project.configuration)
    except Exception as e:
        raise Exception("Failed to download project configuration for job '%s'" % job.name)

    environment.set_value('TASK_NAME', task_name)
    environment.set_value('TASK_ARGUMENT', task_argument)
    environment.set_value('JOB_ID', job.id)
    environment.set_value('TASK_ID', task.id)

    if not job.platform:
        error_string = "No platform set for job '%s'" % job.name
        logs.log_error(error_string)
        raise errors.BadStateError(error_string)

    fuzzer_name = None
    if task_name == 'fuzz':
        fuzzer_name = task_argument
        environment.set_value("FUZZER_NAME", fuzzer_name)
        
    elif task_name == 'corpus_pruning':
            full_fuzzer_name = task_argument
            fuzzer_name, binary = full_fuzzer_name.split(',')

    # Get job's environment string.
    environment_string = job.get_environment_string()

    if task_name == 'minimize':
        job_environment = job.get_environment()
        minimize_job_override = job_environment.get('MINIMIZE_JOB_OVERRIDE')
        if minimize_job_override:
            minimize_job = job
            if minimize_job:
                environment.set_value('JOB_ID', minimize_job_override)
                environment_string = minimize_job.get_environment_string()
                environment_string += '\nORIGINAL_JOB_ID = %s\n' % job.name
                job.name = minimize_job_override
            else:
                logs.log_error(
                    'Job for minimization not found: %s.' % minimize_job_override)

        minimize_fuzzer_override = job_environment.get('MINIMIZE_FUZZER_OVERRIDE')
        fuzzer_name = minimize_fuzzer_override or fuzzer_name

    if fuzzer_name and not environment.is_engine_fuzzer_job(fuzzer_name):
        fuzzer = api_client.fuzzer_api.get_fuzzer(fuzzer_name)
        additional_default_variables = ''
        additional_variables_for_job = ''
        if (fuzzer and hasattr(fuzzer, 'additional_environment_string') and
                fuzzer.additional_environment_string):
            for line in fuzzer.additional_environment_string.splitlines():
                if '=' in line and ':' in line.split('=', 1)[0]:
                    fuzzer_job_name, environment_definition = line.split(':', 1)
                    if fuzzer_job_name == job.name:
                        additional_variables_for_job += '\n%s' % environment_definition
                    continue

                additional_default_variables += '\n%s' % line

        environment_string += additional_default_variables
        environment_string += additional_variables_for_job

    # Update environment for the job.
    update_environment_for_job(environment_string)

    if not is_supported_cpu_arch_for_job():
        logs.log(
            'Unsupported cpu architecture specified in job definition, exiting.')
        tasks.add_task(
            task_name,
            task_argument,
            job.id,
            wait_time=utils.random_number(1, TASK_RETRY_WAIT_LIMIT))
        return

    context = TaskContext(
        task=task, 
        project=project,
        job=job,
        fuzzer_name=fuzzer_name)
    run_command(context)
