
"""Common functions for task creation for test cases."""
from pingu_sdk.datastore.models import Testcase
from pingu_sdk.datastore.models.testcase_variant import TestcaseVariantStatus
from pingu_sdk.build_management.build_managers import build_utils
from pingu_sdk.datastore import data_handler
from pingu_sdk.system import environment, tasks
from pingu_sdk.utils import utils
from pingu_sdk.datastore.data_constants import TaskState
from pingu_sdk.datastore.pingu_api.pingu_api_client import get_api_client

def mark_unreproducible_if_flaky(testcase: Testcase, potentially_flaky):
    """Check to see if a test case appears to be flaky."""
    task_name = environment.get_value('TASK_NAME')

    # If this run does not suggest that we are flaky, clear the flag and assume
    # that we are reproducible.
    if not potentially_flaky:
        testcase.set_metadata('potentially_flaky', False)
        return

    # If we have not been marked as potentially flaky in the past, don't mark
    # mark the test case as unreproducible yet. It is now potentially flaky.
    if not testcase.get_metadata('potentially_flaky'):
        testcase.set_metadata('potentially_flaky', True)

        # In this case, the current task will usually be in a state where it cannot
        # be completed. Recreate it.
        tasks.add_task(task_name, str(testcase.id), testcase.job_id)
        return

    # At this point, this test case has been flagged as potentially flaky twice.
    # It should be marked as unreproducible. Mark it as unreproducible, and set
    # fields that cannot be populated accordingly.
    if task_name == 'minimize' and not testcase.minimized_keys:
        testcase.minimized_keys = 'NA'
    #if task_name in ['minimize', 'impact']:
    #    testcase.set_impacts_as_na()
    if task_name in ['minimize', 'regression']:
        testcase.regression = 'NA'
    if task_name in ['minimize', 'progression']:
        testcase.fixed = 'NA'

    testcase.one_time_crasher_flag = True
    data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                         'Testcase appears to be flaky')

    # Issue update to flip reproducibility label is done in App Engine cleanup
    # cron. This avoids calling the issue tracker apis from GCE.


def create_minimize_task_if_needed(testcase: Testcase):
    """Creates a minimize task if needed."""
    tasks.add_task(command='minimize', argument=testcase.id, job_type=testcase.job_id)


def create_regression_task_if_needed(testcase):
    """Creates a regression task if needed."""
    # We cannot run regression job for custom binaries since we don't have any
    # archived builds for previous revisions. We only track the last uploaded
    # custom build.
    if build_utils.is_custom_binary():
        return

    tasks.add_task('regression', str(testcase.id), testcase.job_id)


def create_variant_tasks_if_needed(testcase: Testcase):
    """Creates a variant task if needed."""
    if testcase.duplicate_of:
        # If another testcase exists with same params, no need to spend cycles on
        # calculating variants again.
        return

    testcase_id = str(testcase.id)
    project = data_handler.get_project_name(testcase.job_id)
    api_client = get_api_client()
    jobs = api_client.job_api.get_jobs()
    for job in jobs:
        # The variant needs to be tested in a different job type than us.
        current_job_id = job.name
        if testcase.job_id == current_job_id:
            continue

        # Don't try to reproduce engine fuzzer testcase with blackbox fuzzer
        # testcases and vice versa.
        if (environment.is_engine_fuzzer_job(testcase.job_id) !=
                environment.is_engine_fuzzer_job(current_job_id)):
            continue

        # Skip experimental jobs.
        job_environment = job.get_environment()
        if utils.string_is_true(job_environment.get('EXPERIMENTAL')):
            continue

        queue = tasks.queue_for_platform(job.platform)
        tasks.add_task('variant', testcase_id, current_job_id, queue)

        variant = api_client.testcase_variant_api.get_testcase_variant(testcase_id, current_job_id)
        variant.status = TestcaseVariantStatus.PENDING
        api_client.testcase_variant_api.add_testcase_variant(variant)


def create_symbolize_task_if_needed(testcase: Testcase):
    """Creates a symbolize task if needed."""
    # We cannot run symbolize job for custom binaries since we don't have any
    # archived symbolized builds.
    if build_utils.is_custom_binary():
        return

    # Make sure we have atleast one symbolized url pattern defined in job type.
    if not build_utils.has_symbolized_builds():
        return

    tasks.add_task('symbolize', str(testcase.id), testcase.job_id)


def create_tasks(testcase: Testcase):
    """Create tasks like minimization, regression, impact, progression, stack
  stack for a newly generated testcase."""
    # No need to create progression task. It is automatically created by the cron
    # handler for reproducible testcases.

    # For a non reproducible crash.
    if testcase.one_time_crasher_flag:
        # For unreproducible testcases, it is still beneficial to get component
        return

    # For a fully reproducible crash.

    # MIN environment variable defined in a job definition indicates if
    # we want to do the heavy weight tasks like minimization, regression,
    # impact, etc on this testcase. These are usually skipped when we have
    # a large timeout and we can't afford to waste more than a couple of hours
    # on these jobs.
    testcase_id = testcase.id
    if environment.get_value('MIN') == 'No':
        api_client = get_api_client()
        testcase = api_client.testcase_api.get_testcase_by_id(testcase_id=testcase_id)
        testcase.minimized_keys = 'NA'
        testcase.regression = 'NA'
        api_client.testcase_api.update_testcase(testcase=testcase)
        return

    # Just create the minimize task for now. Once minimization is complete, it
    # automatically created the rest of the needed tasks.
    create_minimize_task_if_needed(testcase=testcase)


def create_impact_task_if_needed(testcase: Testcase):
    """Creates an impact task if needed."""
    # We cannot run impact job for custom binaries since we don't have any
    # archived production builds for these.
    if build_utils.is_custom_binary():
        return

    tasks.add_task('impact', str(testcase.id), testcase.job_id)
