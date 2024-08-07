
"""Fuzzer log utilities."""

import datetime

from bot.datastore import storage
from bot.metrics import logs
from bot.system import environment

DATE_FORMAT = '%Y-%m-%d'
TIME_FORMAT = '%H:%M:%S:%f'

LOG_EXTENSION = '.log'
LOG_PATH_FORMAT = DATE_FORMAT + '/' + TIME_FORMAT


def get_bucket():
    """Return path to fuzzer logs bucket."""
    return ''


def get_log_relative_path(log_time, file_extension=None):
    """Generate a relative path for a log using the given time.
  Args:
    log_time: A datetime object.
    file_extension: A string appended to the end of the log file name.
      LOG_EXTENSION is used if None.
  Returns:
    A string containing name of the log file.
  """
    if file_extension is None:
        file_extension = LOG_EXTENSION

    return log_time.strftime(LOG_PATH_FORMAT) + file_extension


def get_logs_directory(bucket_name, fuzzer_name, job_type=None, logs_date=None):
    """Get directory path of logs for a given fuzzer/job.
  Args:
    bucket_name: Bucket logs are stored in.
    fuzzer_name: Name of the fuzzer.
    job_type: Job name.
    logs_date: Optional datetime.date for the logs.

  Returns:
    A cloud storage path to the directory containing the desired logs. Format
    returned is /{bucket name}/{path}.
  """
    path = '/%s/%s' % (bucket_name, fuzzer_name)
    if job_type:
        path += '/%s' % job_type

    if logs_date is not None:
        assert job_type is not None
        path += '/%s' % logs_date

    return path


def upload_to_logs(bucket_name,
                   contents,
                   time=None,
                   fuzzer_name=None,
                   job_type=None,
                   file_extension=None, MINIOPREFIX="http://"):
    """Upload file contents to log directory in GCS bucket.
  Args:
    bucket_name: Bucket logs are stored in.
    contents: String containing log to be uploaded.
    time: A datetime object used to generate filename for the log.
    fuzzer_name: Name of the fuzzer. If None, gets this from the environment.
    job_type: Job name. If None, gets this from the environment.
    file_extension: A string appended to the end of the log filename. A default
      value is used if None.

  Returns:
    The path of the uploaded file and whether the uploaded succeeded.
  """
    if not fuzzer_name:
        fuzzer_name = environment.get_value('FUZZER_NAME')

    if not job_type:
        job_type = environment.get_value('JOB_NAME')

    log_directory = get_logs_directory(bucket_name, fuzzer_name, job_type)

    if not time:
        time = datetime.datetime.utcnow()

    log_path = MINIOPREFIX + environment.get_value("MINIO_HOST") + log_directory + '/' + get_log_relative_path(
        time, file_extension)

    if storage.write_data(contents, log_path):
        logs.log('Uploaded file to logs bucket.', log_path=log_path)
    else:
        logs.log_error('Failed to write file to logs bucket.', log_path=log_path)


def upload_script_log(log_contents, fuzzer_name=None, job_type=None):
    """Upload logs to script logs GCS bucket.
  Args:
    log_contents: String containing log to be uploaded.
    fuzzer_name: Name of the fuzzer. If None, gets this from the environment.
    job_type: Job name. If None, gets this from the environment.
  """
    logs_bucket = get_bucket()
    if logs_bucket and log_contents and log_contents.strip():
        upload_to_logs(
            logs_bucket, log_contents, fuzzer_name=fuzzer_name, job_type=job_type)
