
"""Update task for updating source and tests."""

import datetime
import os
import platform
import sys
import time
import zipfile

from bot.datastore import data_handler, storage
from bot.metrics import monitoring_metrics, logs
from bot.system import shell, environment, process_handler, persistent_cache, tasks, archive
from bot.utils import utils, dates
from bot.init_scripts import android as android_init
from bot.init_scripts import linux as linux_init
from bot.init_scripts import windows as windows_init

TESTS_LAST_UPDATE_KEY = 'tests_last_update'
TESTS_UPDATE_INTERVAL_DAYS = 1

MANIFEST_FILENAME = 'bot-source.manifest'
if sys.version_info.major == 3:
    MANIFEST_FILENAME += '.3'


def _rename_dll_for_update(absolute_filepath):
    """Rename a DLL to allow for updates."""
    backup_filepath = absolute_filepath + '.bak.' + str(int(time.time()))
    os.rename(absolute_filepath, backup_filepath)


def _platform_deployment_filename():
    """Return the platform deployment filename."""
    platform_mappings = {
        'Linux': 'linux',
        'Windows': 'windows',
        'Darwin': 'macos'
    }

    base_filename = platform_mappings[platform.system()]
    if sys.version_info.major == 3:
        base_filename += '-3'

    return base_filename + '.zip'


def clear_old_files(directory, extracted_file_set):
    """Remove files from the directory that isn't in the given file list."""
    for root_directory, _, filenames in shell.walk(directory):
        for filename in filenames:
            file_path = os.path.join(root_directory, filename)
            if file_path not in extracted_file_set:
                shell.remove_file(file_path)

    shell.remove_empty_directories(directory)


def clear_pyc_files(directory):
    """Recursively remove all .pyc files from the given directory"""
    for root_directory, _, filenames in shell.walk(directory):
        for filename in filenames:
            if not filename.endswith('.pyc'):
                continue

            file_path = os.path.join(root_directory, filename)
            shell.remove_file(file_path)


def run_platform_init_scripts():
    """Run platform specific initialization scripts."""
    logs.log('Running platform initialization scripts.')

    plt = environment.platform()
    if environment.is_android_emulator():
        # Nothing to do here since emulator is not started yet.
        pass
    elif environment.is_android():
        android_init.run()
    elif plt == 'LINUX':
        linux_init.run()
    elif plt == 'WINDOWS':
        windows_init.run()
    else:
        raise RuntimeError('Unsupported platform')

    logs.log('Completed running platform initialization scripts.')


def update_source_code():
    """Updates source code files with latest version from appengine."""
    process_handler.cleanup_stale_processes()
    shell.clear_temp_directory()

    root_directory = environment.get_value('ROOT_DIR')
    temp_directory = environment.get_value('BOT_TMPDIR')
    temp_archive = os.path.join(temp_directory, 'bot-source.zip')
    try:
        storage.copy_file_from('get_source_url()', temp_archive)
    except Exception:
        logs.log_error('Could not retrieve source code archive from url.')
        return

    try:
        file_list = archive.get_file_list(temp_archive)
        zip_archive = zipfile.ZipFile(temp_archive, 'r')
    except Exception:
        logs.log_error('Bad zip file.')
        return

    src_directory = os.path.join(root_directory, 'src')
    output_directory = os.path.dirname(root_directory)
    error_occurred = False
    normalized_file_set = set()
    for filepath in file_list:
        filename = os.path.basename(filepath)

        # This file cannot be updated on the fly since it is running as server.
        if filename == 'adb':
            continue

        absolute_filepath = os.path.join(output_directory, filepath)
        if os.path.altsep:
            absolute_filepath = absolute_filepath.replace(os.path.altsep, os.path.sep)

        if os.path.realpath(absolute_filepath) != absolute_filepath:
            continue

        normalized_file_set.add(absolute_filepath)
        try:
            file_extension = os.path.splitext(filename)[1]

            # Remove any .so files first before overwriting, as they can be loaded
            # in the memory of existing processes. Overwriting them directly causes
            # segfaults in existing processes (e.g. run.py).
            if file_extension == '.so' and os.path.exists(absolute_filepath):
                os.remove(absolute_filepath)

            # On Windows, to update DLLs (and native .pyd extensions), we rename it
            # first so that we can install the new version.
            if (environment.platform() == 'WINDOWS' and
                    file_extension in ['.dll', '.pyd'] and
                    os.path.exists(absolute_filepath)):
                _rename_dll_for_update(absolute_filepath)
        except Exception:
            logs.log_error('Failed to remove or move %s before extracting new '
                           'version.' % absolute_filepath)

        try:
            extracted_path = zip_archive.extract(filepath, output_directory)
            external_attr = zip_archive.getinfo(filepath).external_attr
            mode = (external_attr >> 16) & 0o777
            mode |= 0o440
            os.chmod(extracted_path, mode)
        except:
            error_occurred = True
            logs.log_error(
                'Failed to extract file %s from source archive.' % filepath)

    zip_archive.close()

    if error_occurred:
        return

    clear_pyc_files(src_directory)
    clear_old_files(src_directory, normalized_file_set)

    local_manifest_path = os.path.join(root_directory,
                                       utils.LOCAL_SOURCE_MANIFEST)
    source_version = utils.read_data_from_file(
        local_manifest_path, eval_data=False).decode('utf-8').strip()
    logs.log('Source code updated to %s.' % source_version)


def run():
    """Run update task."""
    # Since this code is particularly sensitive for bot stability, continue
    # execution but store the exception if anything goes wrong during one of these
    # steps.
    try:
        # Update heartbeat with current time.
        data_handler.update_heartbeat()

        # Check overall free disk space. If we are running too low, clear all
        # data directories like builds, fuzzers, data bundles, etc.
        shell.clear_data_directories_on_low_disk_space()

    except Exception as e:
        logs.log_error(e)
        logs.log_error('Error occurred while running update task.')

        # Run platform specific initialization scripts.
        run_platform_init_scripts()
    except Exception:
        logs.log_error('Error occurred while running update task.')
