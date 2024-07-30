
"""Unpack task for unpacking a multi-testcase archive
from user upload."""

import json
import os

from bot.datastore import data_types, data_handler
from bot.metrics import logs
from bot.system import environment, tasks, archive, shell


def execute_task(job_type):
    bot_name = environment.get_value('BOT_NAME')

    job = data_types.Job.query(data_types.Job.name == job_type).get()
    if not job:
        logs.log_error('Invalid job_type %s.' % job_type)
        return

    testcases_directory = environment.get_value('FUZZ_INPUTS_DISK')
    # Retrieve multi-testcase archive.
    archive_path = os.path.join(testcases_directory)

    file_list = archive.get_file_list(archive_path)

    for file_path in file_list:
        absolute_file_path = os.path.join(testcases_directory, file_path)
        filename = os.path.basename(absolute_file_path)

        # Only files are actual testcases. Skip directories.
        if not os.path.isfile(absolute_file_path):
            continue

        file_handle = open(absolute_file_path, 'rb')
        testcase_file = file_handle.read()

        data_handler.create_user_uploaded_testcase()

    shell.clear_testcase_directories()
