
"""Common helper functions for setup at the start of tasks."""

import base64
import datetime
import os
from pathlib import Path
import shlex
import subprocess
import time
import zipfile

import six

from pingu_sdk.datastore import blobs_manager as blobs
from pingu_sdk.datastore.models import Testcase, Fuzzer, DataBundle
from pingu_sdk import testcase_manager
from pingu_sdk.build_management import revisions
from pingu_sdk.datastore import data_handler
from pingu_sdk.fuzzing import leak_blacklist
from pingu_sdk.metrics import logs, fuzzer_logs
from pingu_sdk.platforms import android
from pingu_sdk.system import environment, shell, errors, tasks, archive
from pingu_sdk.utils import utils, dates
from pingu_sdk.datastore.data_constants import TaskState, ArchiveStatus
from pingu_sdk.datastore.pingu_api.pingu_api_client import get_api_client

_BOT_DIR = 'working_directory'
_DATA_BUNDLE_CACHE_COUNT = 10
_DATA_BUNDLE_SYNC_INTERVAL_IN_SECONDS = 6 * 60 * 60
_DATA_BUNDLE_LOCK_INTERVAL_IN_SECONDS = 3 * 60 * 60
_SYNC_FILENAME = '.sync'
_TESTCASE_ARCHIVE_EXTENSION = '.zip'


def _copy_testcase_to_device_and_setup_environment(testcase,
                                                   testcase_file_path):
    """Android specific setup steps for testcase."""
    # Copy test(s) to device.
    android.device.push_testcases_to_device()

    # The following steps need privileged job access.
    job_type_has_privileged_access = environment.get_value('PRIVILEGED_ACCESS')
    if not job_type_has_privileged_access:
        return

    # Install testcase if it is an app.
    package_name = android.app.get_package_name(testcase_file_path)
    if package_name:
        # Set the package name for later use.
        environment.set_value('PKG_NAME', package_name)

        # Install the application apk.
        android.device.install_application_if_needed(
            testcase_file_path, force_update=True)

    # Set app launch command if available from upload.
    app_launch_command = testcase.get_metadata('app_launch_command')
    if app_launch_command:
        environment.set_value('APP_LAUNCH_COMMAND', app_launch_command)

    # Set executable bit on the testcase (to allow binary executable testcases
    # to work in app launch command, e.g. shell %TESTCASE%).
    local_testcases_directory = environment.get_value('FUZZ_INPUTS')
    if (testcase_file_path and
            testcase_file_path.startswith(local_testcases_directory)):
        relative_testcase_file_path = (
            testcase_file_path[len(local_testcases_directory) + 1:])
        device_testcase_file_path = os.path.join(
            android.constants.DEVICE_TESTCASES_DIR, relative_testcase_file_path)
        android.adb.run_shell_command(['chmod', '0755', device_testcase_file_path])


def _get_application_arguments(testcase: Testcase, job_id, task_name):
    """Get application arguments to use for setting up |testcase|. Use minimized
   arguments if available. For variant task, where we run a testcase against
   another job type, use both minimized arguments and application arguments
   from job."""
    testcase_args = testcase.minimized_arguments
    if not testcase_args:
        return None

    if task_name != 'variant':
        return testcase_args

    # TODO(aarya): Use %TESTCASE% explicitly since it will not exist with new
    # engine impl libFuzzer testcases and AFL's launcher.py requires it as the
    # first argument. Remove once AFL is migrated to the new engine impl.
    if environment.is_afl_job(job_id):
        return '%TESTCASE%'

    job_args = data_handler.get_value_from_job_definition(
        job_id, 'APP_ARGS', default='')
    job_args_list = shlex.split(job_args)
    testcase_args_list = shlex.split(testcase_args)
    testcase_args_filtered_list = [
        arg for arg in testcase_args_list if arg not in job_args_list
    ]

    app_args = ' '.join(testcase_args_filtered_list)
    if job_args:
        if app_args:
            app_args += ' '
        app_args += job_args

    return app_args


def _setup_memory_tools_environment(testcase: Testcase):
    """Set up environment for various memory tools used."""
    env = testcase.get_metadata('env')
    if not env:
        environment.reset_current_memory_tool_options(
            redzone_size=testcase.redzone, disable_ubsan=testcase.disable_ubsan)
        return

    for options_name, options_value in six.iteritems(env):
        if not options_value:
            environment.remove_key(options_name)
            continue
        environment.set_memory_tool_options(options_name, options_value)


def prepare_environment_for_testcase(testcase: Testcase, job_id, task_name):
    """Set various environment variables based on the test case."""
    _setup_memory_tools_environment(testcase)

    # Setup environment variable for windows size and location properties.
    # Explicit override to avoid using the default one from job definition since
    # that contains unsubsituted vars like $WIDTH, etc.
    #environment.set_value('WINDOW_ARG', testcase.window_argument)

    # Adjust timeout based on the stored multiplier (if available).
    if testcase.timeout_multiplier:
        test_timeout = environment.get_value('TEST_TIMEOUT')
        environment.set_value('TEST_TIMEOUT',
                              int(test_timeout * testcase.timeout_multiplier))

    # Add FUZZ_TARGET to environment if this is a fuzz target testcase.
    fuzz_target = testcase.get_metadata('fuzzer_binary_name')
    if fuzz_target:
        environment.set_value('FUZZ_TARGET', fuzz_target)

    # Override APP_ARGS with minimized arguments (if available). Don't do this
    # for variant task since other job types can have its own set of required
    # arguments, so use the full set of arguments of that job.
    app_args = _get_application_arguments(testcase, job_id, task_name)
    if app_args:
        environment.set_value('APP_ARGS', app_args)


def setup_testcase(testcase: Testcase, job_id, fuzzer_override=None):
    """Sets up the testcase and needed dependencies like fuzzer,
  data bundle, etc."""
    api_client = get_api_client()
    fuzzer = api_client.fuzzer_api.get_fuzzer_by_id(str(testcase.fuzzer_id))
    fuzzer_name = fuzzer_override or fuzzer.name
    task_name = environment.get_value('TASK_NAME')
    testcase_fail_wait = environment.get_value('FAIL_WAIT')
    testcase_id = str(testcase.id)

    # Clear testcase directories.
    shell.clear_testcase_directories()

    # Update the fuzzer if necessary in order to get the updated data bundle.
    if fuzzer_name:
        try:
            update_successful = update_fuzzer_and_data_bundles(fuzzer)
        except errors.InvalidFuzzerError:
            # Close testcase and don't recreate tasks if this fuzzer is invalid.
            testcase.open = False
            testcase.fixed = 'NA'
            testcase.set_metadata('fuzzer_was_deleted', True)
            logs.log_error('Closed testcase %d with invalid fuzzer %s.' %
                           (testcase_id, fuzzer_name))

            error_message = 'Fuzzer %s no longer exists' % fuzzer_name
            data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                                 error_message)
            return None, None, None

        if not update_successful:
            error_message = 'Unable to setup fuzzer %s' % fuzzer_name
            data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                                 error_message)
            tasks.add_task(
                task_name, testcase_id, job_id, wait_time=testcase_fail_wait)
            return None, None, None

    # Extract the testcase and any of its resources to the input directory.
    file_list, input_directory, testcase_file_path = unpack_testcase(testcase)
    if not file_list:
        error_message = 'Unable to setup testcase %s' % testcase_file_path
        data_handler.update_testcase_comment(testcase, TaskState.ERROR,
                                             error_message)
        tasks.add_task(
            task_name, testcase_id, job_id, wait_time=testcase_fail_wait)
        return None, None, None

    # For Android/Fuchsia, we need to sync our local testcases directory with the
    # one on the device.
    if environment.is_android():
        _copy_testcase_to_device_and_setup_environment(testcase, testcase_file_path)

    # Copy global blacklist into local blacklist.
    is_lsan_enabled = environment.get_value('LSAN')
    if is_lsan_enabled:
        # Get local blacklist without this testcase's entry.
        leak_blacklist.copy_global_to_local_blacklist(excluded_testcase=testcase)

    fuzzer = api_client.fuzzer_api.get_fuzzer_by_id(str(testcase.fuzzer_id))
    environment.set_value("FUZZER_NAME", fuzzer.name)
    prepare_environment_for_testcase(testcase, job_id, task_name)

    return file_list, input_directory, testcase_file_path


def _get_testcase_file_and_path(testcase: Testcase):
    """Figure out the relative path and input directory for this testcase."""
    testcase_absolute_path = testcase.absolute_path

    # This hack is needed so that we can run a testcase generated on windows, on
    # linux. os.path.isabs return false on paths like c:\a\b\c.
    testcase_path_is_absolute = (
            testcase_absolute_path[1:3] == ':\\' or
            os.path.isabs(testcase_absolute_path))

    # Fix os.sep in testcase path if we are running this on non-windows platform.
    # It is unusual to have '\\' on linux paths, so substitution should be safe.
    if environment.platform() != 'WINDOWS' and '\\' in testcase_absolute_path:
        testcase_absolute_path = testcase_absolute_path.replace('\\', os.sep)

    # Default directory for testcases.
    input_directory = environment.get_value('FUZZ_INPUTS')
    if not testcase_path_is_absolute:
        testcase_path = os.path.join(input_directory, os.path.basename(testcase_absolute_path))
        return input_directory, testcase_path

    # Check if the testcase is on a nfs data bundle. If yes, then just
    # return it without doing root directory path fix.
    nfs_root = environment.get_value('NFS_ROOT')
    if nfs_root and testcase_absolute_path.startswith(nfs_root):
        return input_directory, testcase_absolute_path

    # Root directory can be different on bots. Fix the path to account for this.
    root_directory = environment.get_value('ROOT_DIR')
    if not root_directory:
        raise Exception("ROOT_DIR is not set in environment.")
    if testcase_absolute_path.startswith(root_directory):
        return input_directory, testcase_absolute_path[len(root_directory) + 1:]
    else:
        # If the root directory is not set correctly, we should fix it here.
        testcase_path = os.path.join(input_directory, testcase_absolute_path)
    

    return input_directory, testcase_path


def unpack_testcase(testcase: Testcase):
    """Unpack a testcase and return all files it is composed of."""
    # Figure out where the testcase file should be stored.
    input_directory, testcase_file_path = _get_testcase_file_and_path(testcase)

    minimized = testcase.minimized_keys and testcase.minimized_keys != 'NA'
    if minimized:
        key = testcase.minimized_keys
        archived = bool(testcase.archive_state & ArchiveStatus.MINIMIZED)
    else:
        key = testcase.fuzzed_keys
        archived = bool(testcase.archive_state & ArchiveStatus.FUZZED)

    if archived:
        if minimized:
            temp_filename = (
                os.path.join(input_directory,
                             str(testcase.id) + _TESTCASE_ARCHIVE_EXTENSION))
        else:
            temp_filename = os.path.join(input_directory, testcase.archive_filename)
    else:
        temp_filename = testcase_file_path

    # if not blobs.read_blob_to_disk(key, temp_filename):
    #     return None, input_directory, testcase_file_path

    file_list = []
    if archived:
        archive.unpack(temp_filename, input_directory)
        file_list = archive.get_file_list(temp_filename)
        shell.remove_file(temp_filename)

        file_exists = False
        for file_name in file_list:
            if os.path.basename(file_name) == os.path.basename(testcase_file_path):
                file_exists = True
                break

        if not file_exists:
            logs.log_error(
                'Expected file to run %s is not in archive. Base directory is %s and '
                'files in archive are [%s].' % (testcase_file_path, input_directory,
                                                ','.join(file_list)))
            return None, input_directory, testcase_file_path
    else:
        file_list.append(testcase_file_path)

    for file_path in file_list:
        if not os.path.exists(file_path):
            testcase_data = base64.b64decode(testcase.test_case)
            utils.write_data_to_file(testcase_data, file_path)

    return file_list, input_directory, testcase_file_path


def _get_data_bundle_update_lock_name(data_bundle_name):
    """Return the lock key name for the given data bundle."""
    return 'update:data_bundle:%s' % data_bundle_name


def _get_data_bundle_sync_file_path(data_bundle_directory):
    """Return path to data bundle sync file."""
    return os.path.join(data_bundle_directory, _SYNC_FILENAME)


def _clear_old_data_bundles_if_needed():
    """Clear old data bundles so as to keep the disk cache restricted to
  |_DATA_BUNDLE_CACHE_COUNT| data bundles and prevent potential out-of-disk
  spaces."""
    data_bundles_directory = environment.get_value('DATA_BUNDLES_DIR')

    dirs = []
    for filename in os.listdir(data_bundles_directory):
        file_path = os.path.join(data_bundles_directory, filename)
        if not os.path.isdir(file_path):
            continue
        dirs.append(file_path)

    dirs_to_remove = sorted(
        dirs, key=os.path.getmtime, reverse=True)[_DATA_BUNDLE_CACHE_COUNT:]
    for dir_to_remove in dirs_to_remove:
        logs.log('Removing data bundle directory to keep disk cache small: %s' %
                 dir_to_remove)
        shell.remove_directory(dir_to_remove)

def _set_fuzzer_env_vars(fuzzer: Fuzzer):
  """Sets fuzzer env vars for fuzzer set up."""
  #environment.set_value('UNTRUSTED_CONTENT', fuzzer.untrusted_content)
  # Adjust the test timeout, if user has provided one.
  if fuzzer.timeout:
    environment.set_value('TEST_TIMEOUT', fuzzer.timeout)

    # Increase fuzz test timeout if the fuzzer timeout is higher than its
    # current value.
    fuzz_test_timeout = environment.get_value('FUZZ_TEST_TIMEOUT')
    if fuzz_test_timeout and fuzz_test_timeout < fuzzer.timeout:
      environment.set_value('FUZZ_TEST_TIMEOUT', fuzzer.timeout)

  # Adjust the max testcases if this fuzzer has specified a lower limit.
  max_testcases = environment.get_value('MAX_TESTCASES')
  if max_testcases and fuzzer.max_testcases and fuzzer.max_testcases < max_testcases:
    environment.set_value('MAX_TESTCASES', fuzzer.max_testcases)

  # If the fuzzer generates large testcases or a large number of small ones
  # that don't fit on tmpfs, then use the larger disk directory.
  if fuzzer.has_large_testcases:
    testcase_disk_directory = environment.get_value('FUZZ_INPUTS_DISK')
    environment.set_value('FUZZ_INPUTS', testcase_disk_directory)


def _update_fuzzer(
    fuzzer: Fuzzer,  # pylint: disable=no-member
    fuzzer_directory: str,
    version_file: str) -> bool:
  
    """Updates the fuzzer. Helper for update_fuzzer_and_data_bundles."""
    if fuzzer.builtin:
        return True

    if not revisions.needs_update(version_file, fuzzer.revision):
        return True

    logs.log('Fuzzer update was found, updating.')

    # Clear the old fuzzer directory if it exists.
    if not shell.remove_directory(fuzzer_directory, recreate=True):
        logs.log_error('Failed to clear fuzzer directory.')
        return False

    # Copy the archive to local disk and unpack it.
    archive_path = os.path.join(fuzzer_directory, fuzzer.filename)
    fuzzer_stream = get_api_client().fuzzer_api.download_fuzzer(fuzzer.id)
    utils.write_data_to_file(content=fuzzer_stream, file_path=archive_path)
    try:
        archive.unpack(
            archive_path,
            fuzzer_directory,
            trusted=True)
    except:
        error_message = (f'Failed to unpack fuzzer archive {fuzzer.filename} '
                        '(bad archive or unsupported format).')
        logs.log_error(error_message)
        return False
    
    if fuzzer.install_script:
        fuzzer_installer_path = os.path.join(fuzzer_directory, fuzzer.install_script)
        os.chmod(fuzzer_installer_path, 0o755)
        base_dir, build_script = os.path.split(fuzzer_installer_path)
        command = "./" + build_script
        try:
            p = subprocess.Popen(
                command, stdout=subprocess.PIPE, shell=True, cwd=base_dir)
        except Exception as e:
            logs.log_error(e)

    fuzzer_path = os.path.join(fuzzer_directory, fuzzer.executable_path)
    if not os.path.exists(fuzzer_path):
        error_message = ('Fuzzer executable %s not found. '
                            'Check fuzzer configuration.') % fuzzer.executable_path
        logs.log_error(error_message)
        fuzzer_logs.upload_script_log(
            'Fatal error: ' + error_message,
            fuzzer_name=fuzzer.name,
            )
        return False

    # Make fuzzer executable.
    os.chmod(fuzzer_path, 0o750)

    # Cleanup unneeded archive.
    shell.remove_file(archive_path)

    # Save the current revision of this fuzzer in a file for later checks.
    revisions.write_revision_to_revision_file(version_file, fuzzer.revision)
    logs.log('Updated fuzzer to revision %d.' % fuzzer.revision)
    return True

def _set_up_data_bundles(fuzzer, data_bundle_corpuses):  # pylint: disable=no-member
    """Sets up data bundles. Helper for update_fuzzer_and_data_bundles."""
    # Setup data bundles associated with this fuzzer.
    logs.log_warn('Setting up data bundles.')
    for data_bundle_corpus in data_bundle_corpuses:
        if not update_data_bundle(fuzzer, data_bundle_corpus):
            return False
    return True

def update_data_bundle(fuzzer: Fuzzer, data_bundle: DataBundle):
    """Updates a data bundle to the latest version."""
    # This module can't be in the global imports due to appengine issues
    # with multiprocessing and psutil imports.

    # If we are using a data bundle on NFS, it is expected that our testcases
    # will usually be large enough that we would fill up our tmpfs directory
    # pretty quickly. So, change it to use an on-disk directory.
    if not data_bundle.is_local:
        testcase_disk_directory = environment.get_value('FUZZ_INPUTS_DISK')
        environment.set_value('FUZZ_INPUTS', testcase_disk_directory)

    data_bundle_directory = get_data_bundle_directory(fuzzer.name)
    if not data_bundle_directory:
        logs.log_error('Failed to setup data bundle %s.' % data_bundle.name)
        return False

    if not shell.create_directory(
            data_bundle_directory, create_intermediates=True):
        logs.log_error(
            'Failed to create data bundle %s directory.' % data_bundle.name)
        return False

    # Check if data bundle is up to date. If yes, skip the update.
    if _is_data_bundle_up_to_date(data_bundle, data_bundle_directory):
        logs.log('Data bundle was recently synced, skip.')
        return True

    # Re-check if another bot did the sync already. If yes, skip.
    if _is_data_bundle_up_to_date(data_bundle, data_bundle_directory):
        logs.log('Another bot finished the sync, skip.')
        return True

    time_before_sync_start = time.time()

    # Update the testcase list file.
    testcase_manager.create_testcase_list_file(data_bundle_directory)

    #  Write last synced time in the sync file.
    sync_file_path = _get_data_bundle_sync_file_path(data_bundle_directory)
    utils.write_data_to_file(time_before_sync_start, sync_file_path)

    return True


def update_fuzzer_and_data_bundles(fuzzer: Fuzzer):
    """Update the fuzzer with a given name if necessary."""
    if not fuzzer:
        logs.log_error('No fuzzer exists with name.')
        raise errors.InvalidFuzzerError

    _set_fuzzer_env_vars(fuzzer)
     # Set some helper environment variables.
    fuzzer_directory = get_fuzzer_directory(fuzzer.name)
    environment.set_value('FUZZER_DIR', fuzzer_directory)

    # Check for updates to this fuzzer.
    version_file = os.path.join(fuzzer_directory,
                                f'.{fuzzer.name}_version')
    _update_fuzzer(fuzzer, fuzzer_directory, version_file)
    
    # Check for data bundles updates
    _clear_old_data_bundles_if_needed()
    _set_up_data_bundles(fuzzer, [])

    # Setup environment variable for launcher script path.
    if fuzzer.launcher_script:
        fuzzer_launcher_path = os.path.join(fuzzer_directory,
                                            fuzzer.launcher_script)
        environment.set_value('LAUNCHER_PATH', fuzzer_launcher_path)

    return fuzzer
    


def _is_search_index_data_bundle(data_bundle_name: DataBundle):
    """Return true on if this is a search index data bundle, false otherwise."""
    return data_bundle_name.startswith(
        testcase_manager.SEARCH_INDEX_BUNDLE_PREFIX)


def _is_data_bundle_up_to_date(data_bundle: DataBundle, data_bundle_directory):
    """Return true if the data bundle is up to date, false otherwise."""
    sync_file_path = _get_data_bundle_sync_file_path(data_bundle_directory)

    if not os.path.exists(sync_file_path):
        return False

    last_sync_time = datetime.datetime.utcfromtimestamp(
        utils.read_data_from_file(sync_file_path))

    # Check if we recently synced.
    if not dates.time_has_expired(
            last_sync_time, seconds=_DATA_BUNDLE_SYNC_INTERVAL_IN_SECONDS):
        return True

    # For search index data bundle, we don't sync them from bucket. Instead, we
    # rely on the fuzzer to generate testcases periodically.
    if _is_search_index_data_bundle(data_bundle.name):
        return False

    # Check when the bucket url had last updates. If no new updates, no need to
    # update directory.
"""     bucket_url = get_api_client().databundle_api.get_data_bundle(data_bundle.name)
    last_updated_time = storage.last_updated(bucket_url)
    if last_updated_time and last_sync_time > last_updated_time:
        logs.log(
            'Data bundle %s has no new content from last sync.' % data_bundle.name)
        return True

    return False """


def _get_nfs_data_bundle_path(data_bundle_name):
    """Get  path for a data bundle on NFS."""
    nfs_root = environment.get_value('NFS_ROOT')

    # Special naming and path for search index based bundles.
    if _is_search_index_data_bundle(data_bundle_name):
        return os.path.join(
            nfs_root, testcase_manager.SEARCH_INDEX_TESTCASES_DIRNAME,
            data_bundle_name[len(testcase_manager.SEARCH_INDEX_BUNDLE_PREFIX):])

    return os.path.join(nfs_root, data_bundle_name)


def get_data_bundle_directory(fuzzer: Fuzzer):
    """Return data bundle data directory."""
    # Store corpora for built-in fuzzers like libFuzzer in the same directory
    # as other local data bundles. This makes it easy to clear them when we run
    # out of disk space.
    local_data_bundles_directory = environment.get_value('DATA_BUNDLES_DIR')
    if fuzzer.builtin:
        return local_data_bundles_directory

    # Check if we have a fuzzer-specific data bundle. Use it to calculate the
    # data directory we will fetch our testcases from.
    api_client = get_api_client()
    data_bundle = api_client.databundle_api.get_data_bundle(fuzzer.data_bundle_name)
    if not data_bundle:
        # Generic data bundle directory. Available to all fuzzers if they don't
        # have their own data bundle.
        return environment.get_value('FUZZ_DATA')

    local_data_bundle_directory = os.path.join(local_data_bundles_directory,
                                               data_bundle.name)

    if data_bundle.is_local:
        # Data bundle is on local disk, return path.
        return local_data_bundle_directory

    # This data bundle is on NFS, calculate path.
    # Make sure that NFS_ROOT pointing to nfs server is set. If not, use local.
    if not environment.get_value('NFS_ROOT'):
        logs.log_warn('NFS_ROOT is not set, using local corpora directory.')
        return local_data_bundle_directory

    return _get_nfs_data_bundle_path(data_bundle.name)


def get_fuzzer_directory(fuzzer_name):
    """Return directory used by a fuzzer."""
    fuzzer_directory = environment.get_value('FUZZERS_DIR')
    fuzzer_directory = os.path.join(fuzzer_directory, fuzzer_name)
    return fuzzer_directory


def is_directory_on_nfs(data_bundle_directory):
    """Return whether this directory is on NFS."""
    nfs_root = environment.get_value('NFS_ROOT')
    if not nfs_root:
        return False

    data_bundle_directory_real_path = os.path.realpath(data_bundle_directory)
    nfs_root_real_path = os.path.realpath(nfs_root)
    return data_bundle_directory_real_path.startswith(nfs_root_real_path + os.sep)


def archive_testcase_and_dependencies_in_cs(resource_list, testcase_path, project_id):
    """Archive testcase and its dependencies, and store in blobstore."""
    if not os.path.exists(testcase_path):
        logs.log_error('Unable to find testcase %s.' % testcase_path)
        return None, None, None, None

    absolute_filename = testcase_path
    archived = False
    zip_filename = None
    zip_path = None
    file_size = None

    if not resource_list:
        resource_list = []

    # Add resource dependencies based on testcase path. These include
    # stuff like extensions directory, dependency files, etc.
    resource_list.extend(
        testcase_manager.get_resource_dependencies(testcase_path))

    # Filter out duplicates, directories, and files that do not exist.
    resource_list = utils.filter_file_list(resource_list)

    logs.log('Testcase and related files :\n%s' % str(resource_list))

    if len(resource_list) <= 1:
        # If this does not have any resources, just save the testcase.
        # TODO(flowerhack): Update this when we teach CF how to download testcases.
        try:
            file_handle = open(testcase_path, 'rb')
            file_size = os.stat(testcase_path).st_size
        except IOError:
            logs.log_error('Unable to open testcase %s.' % testcase_path)
            return None, None, None, None
    else:
        # If there are resources, create an archive.

        # Find the common root directory for all of the resources.
        # Assumption: resource_list[0] is the testcase path.
        base_directory_list = resource_list[0].split(os.path.sep)
        for list_index in range(1, len(resource_list)):
            current_directory_list = resource_list[list_index].split(os.path.sep)
            length = min(len(base_directory_list), len(current_directory_list))
            for directory_index in range(length):
                if (current_directory_list[directory_index] !=
                        base_directory_list[directory_index]):
                    base_directory_list = base_directory_list[0:directory_index]
                    break

        base_directory = os.path.sep.join(base_directory_list)
        logs.log('Subresource common base directory: %s' % base_directory)
        if base_directory:
            # Common parent directory, archive sub-paths only.
            base_len = len(base_directory) + len(os.path.sep)
        else:
            # No common parent directory, archive all paths as it-is.
            base_len = 0

        # Prepare the filename for the archive.
        zip_filename, _ = os.path.splitext(os.path.basename(testcase_path))
        zip_filename += _TESTCASE_ARCHIVE_EXTENSION

        # Create the archive.
        zip_path = os.path.join(environment.get_value('INPUT_DIR'), zip_filename)
        zip_file = zipfile.ZipFile(zip_path, 'w')
        for file_name in resource_list:
            if os.path.exists(file_name):
                relative_filename = file_name[base_len:]
                zip_file.write(file_name, relative_filename, zipfile.ZIP_DEFLATED)
        zip_file.close()
        try:
            file_handle = open(zip_path, 'rb')
            file_size = os.stat(zip_path).st_size
        except IOError:
            logs.log_error('Unable to open testcase archive %s.' % zip_path)
            return None, None, None, None

        archived = True
        absolute_filename = testcase_path[base_len:]

    # TODO upload file to nfs
    fuzzed_key = blobs.write_blob(project_id, file_handle, file_size)
    file_handle.close()

    # Don't need the archive after writing testcase to blobstore.
    if zip_path:
        shell.remove_file(zip_path)

    return fuzzed_key, archived, absolute_filename, zip_filename
