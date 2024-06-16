
"""Classes for dealing with FuzzerStats."""

import datetime
import functools
import itertools
import json
import os
import random
import re

from bot.fuzzing.stats_uploader import StatsStorage
from bot.datastore import data_types, data_handler, fuzz_target_utils, storage
from bot.metrics import logs, fuzzer_logs
from bot.system import environment, shell
from bot.utils import utils

STATS_FILE_EXTENSION = '.stats2'

PERFORMANCE_REPORT_VIEWER_PATH = '/performance-report/{fuzzer}/{job}/{date}'

JOB_RUN_SCHEMA = {
    'fields': [{
        'name': 'testcases_executed',
        'type': 'INTEGER',
        'mode': 'NULLABLE'
    }, {
        'name': 'build_revision',
        'type': 'INTEGER',
        'mode': 'NULLABLE'
    }, {
        'name': 'new_crashes',
        'type': 'INTEGER',
        'mode': 'NULLABLE'
    }, {
        'name': 'job',
        'type': 'STRING',
        'mode': 'NULLABLE'
    }, {
        'name': 'timestamp',
        'type': 'FLOAT',
        'mode': 'NULLABLE'
    }, {
        'name':
            'crashes',
        'type':
            'RECORD',
        'mode':
            'REPEATED',
        'fields': [{
            'name': 'crash_type',
            'type': 'STRING',
            'mode': 'NULLABLE'
        }, {
            'name': 'is_new',
            'type': 'BOOLEAN',
            'mode': 'NULLABLE'
        }, {
            'name': 'crash_state',
            'type': 'STRING',
            'mode': 'NULLABLE'
        }, {
            'name': 'security_flag',
            'type': 'BOOLEAN',
            'mode': 'NULLABLE'
        }, {
            'name': 'count',
            'type': 'INTEGER',
            'mode': 'NULLABLE'
        }]
    }, {
        'name': 'known_crashes',
        'type': 'INTEGER',
        'mode': 'NULLABLE'
    }, {
        'name': 'fuzzer',
        'type': 'STRING',
        'mode': 'NULLABLE'
    }, {
        'name': 'kind',
        'type': 'STRING',
        'mode': 'NULLABLE'
    }]
}


class FuzzerStatsException(Exception):
    """Fuzzer stats exception."""


class BaseRun(object):
    """Base run."""

    VALID_FIELDNAME_PATTERN = re.compile(r'[a-zA-Z][a-zA-Z0-9_]*')

    def __init__(self, fuzzer, job, build_revision, timestamp):
        self._stats_data = {
            'fuzzer': fuzzer,
            'job': job,
            'build_revision': build_revision,
            'timestamp': timestamp,
        }

    def __getitem__(self, key):
        return self._stats_data.__getitem__(key)

    def __setitem__(self, key, value):
        if not re.compile(self.VALID_FIELDNAME_PATTERN):
            raise ValueError('Invalid key name.')

        return self._stats_data.__setitem__(key, value)

    def __delitem__(self, key):
        return self._stats_data.__delitem__(key)

    def __contains__(self, key):
        return self._stats_data.__contains__(key)

    def to_json(self):
        """Return JSON representation of the stats."""
        return json.dumps(self._stats_data)

    def update(self, other):
        """Update stats with a dict."""
        self._stats_data.update(other)

    @property
    def data(self):
        return self._stats_data

    @property
    def kind(self):
        return self._stats_data['kind']

    @property
    def fuzzer(self):
        return self._stats_data['fuzzer']

    @property
    def job(self):
        return self._stats_data['job']

    @property
    def build_revision(self):
        return self._stats_data['build_revision']

    @property
    def timestamp(self):
        return self._stats_data['timestamp']

    @staticmethod
    def from_json(json_data):
        """Convert json to the run."""
        try:
            data = json.loads(json_data)
        except (ValueError, TypeError):
            return None

        if not isinstance(data, dict):
            return None

        result = None
        try:
            kind = data['kind']
            if kind == 'TestcaseRun':
                result = TestcaseRun(data['fuzzer'], data['job'],
                                     data['build_revision'], data['timestamp'])
            elif kind == 'JobRun':
                result = JobRun(data['fuzzer'], data['job'], data['build_revision'],
                                data['timestamp'], data['testcases_executed'],
                                data['new_crashes'], data['known_crashes'],
                                data.get('crashes'))
        except KeyError:
            return None

        if result:
            result.update(data)
        return result


class JobRun(BaseRun):
    """Represents stats for a particular job run."""

    SCHEMA = JOB_RUN_SCHEMA

    # `crashes` is a new field that will replace `new_crashes` and `old_crashes`.
    def __init__(self, fuzzer, job, build_revision, timestamp,
                 number_of_testcases, new_crashes, known_crashes, crashes):
        super(JobRun, self).__init__(fuzzer, job, build_revision, timestamp)
        self._stats_data.update({
            'kind': 'JobRun',
            'testcases_executed': number_of_testcases,
            'new_crashes': new_crashes,
            'known_crashes': known_crashes,
            'crashes': crashes
        })


class TestcaseRun(BaseRun):
    """Represents stats for a particular testcase run."""

    SCHEMA = None

    def __init__(self, fuzzer, job, build_revision, timestamp):
        super(TestcaseRun, self).__init__(fuzzer, job, build_revision, timestamp)
        self._stats_data.update({
            'kind': 'TestcaseRun',
        })

        source = environment.get_value('STATS_SOURCE')
        if source:
            self._stats_data['source'] = source

    @staticmethod
    def get_stats_filename(testcase_file_path):
        """Get stats filename for the given testcase."""
        return testcase_file_path + STATS_FILE_EXTENSION

    @staticmethod
    def read_from_disk(testcase_file_path, delete=False):
        """Read the TestcaseRun for the given testcase."""
        stats_file_path = TestcaseRun.get_stats_filename(testcase_file_path)
        if not os.path.exists(stats_file_path):
            return None

        fuzzer_run = None
        with open(stats_file_path) as f:
            fuzzer_run = BaseRun.from_json(f.read())

        if delete:
            shell.remove_file(stats_file_path)

        return fuzzer_run

    @staticmethod
    def write_to_disk(testcase_run, testcase_file_path):
        """Write the given TestcaseRun for |testcase_file_path| to disk."""
        if not testcase_run:
            return

        stats_file_path = TestcaseRun.get_stats_filename(testcase_file_path)
        with open(stats_file_path, 'w') as f:
            f.write(testcase_run.to_json())



def get_coverage_info(fuzzer, date=None):
    """Returns a CoverageInformation entity for a given fuzzer and date. If date
  is not specified, returns the latest entity available."""
    query = data_types.CoverageInformation.query(
        data_types.CoverageInformation.fuzzer == fuzzer)
    if date:
        # Return info for specific date.
        query = query.filter(data_types.CoverageInformation.date == date)
    else:
        # Return latest.
        query = query.order(-data_types.CoverageInformation.date)

    return query.get()


def get_stats_path(job_id, kind, fuzzer, timestamp):
    """Return path in the format "/bucket/path/to/containing_dir/" for the
  given fuzzer, job, and timestamp or revision."""
    bigquery_bucket = environment.get_value('BIGQUERY_BUCKET')
    if not bigquery_bucket:
        return None

    datetime_value = datetime.datetime.utcfromtimestamp(timestamp)
    dir_name = data_types.coverage_information_date_to_string(datetime_value)

    path = '/%s/%s/%s/%s/%s/' % (bigquery_bucket, fuzzer, job_id, kind, dir_name)
    return path


#@environment.local_noop
def upload_stats(stats_list, filename=None):
    """Upload the fuzzer run to the bigquery bucket. Assumes that all the stats
  given are for the same fuzzer/job run."""
    if not stats_list:
        logs.log_error('Failed to upload fuzzer stats: empty stats.')
        return

    assert isinstance(stats_list, list)

    bigquery_bucket = environment.get_value('BIGQUERY_BUCKET')
    if not bigquery_bucket:
        logs.log_error('Failed to upload fuzzer stats: missing bucket name.')
        return

    stats_storage = StatsStorage(bucket_name=bigquery_bucket)
    kind = stats_list[0].kind
    fuzzer = stats_list[0].fuzzer

    # Group all stats for fuzz targets.
    fuzzer_or_engine_name = get_fuzzer_or_engine_name(fuzzer)

    if not filename:
        # Generate a random filename.
        filename = '%016x' % random.randint(0, (1 << 64) - 1) + '.json'

    # Handle runs that bleed into the next day.
    timestamp_start_of_day = lambda s: utils.utc_date_to_timestamp(
        datetime.datetime.utcfromtimestamp(s.timestamp).date())
    stats_list.sort(key=lambda s: s.timestamp)

    for timestamp, stats in itertools.groupby(stats_list, timestamp_start_of_day):
        upload_data = '\n'.join(stat.to_json() for stat in stats)

        day_path = get_stats_path(stats_list[0].job,
            kind, fuzzer_or_engine_name, timestamp=timestamp) + filename

        if not storage.write_data(upload_data.encode('utf-8'), day_path):
            logs.log_error('Failed to upload FuzzerRun.')


def get_fuzzer_or_engine_name(fuzzer_name):
    """Return fuzzing engine name if it exists, or |fuzzer_name|."""
    #fuzz_target = data_handler.get_fuzz_target_by_id(fuzzer_name)
    #if fuzz_target:
    #    return fuzz_target.engine

    return fuzzer_name


def dataset_name(fuzzer_name):
    """Get the stats dataset name for the given |fuzzer_name|."""
    return fuzzer_name.replace('-', '_') + '_stats'
