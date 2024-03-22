
"""Monitoring."""
# pylint: disable=invalid-name
# TODO(ochang): Remove V3 from names once all metrics are migrated to
# stackdriver.

import bisect
import collections
import pandas as pd
import functools
import itertools
import os
import re
import threading
import time

import six

from bot.metrics import logs
from bot.system import environment
from bot.utils import utils

CUSTOM_METRIC_PREFIX = 'bot'
FLUSH_INTERVAL_SECONDS = 10 * 60  # 10 minutes.
RETRY_DEADLINE_SECONDS = 5 * 60  # 5 minutes.
INITIAL_DELAY_SECONDS = 16
MAXIMUM_DELAY_SECONDS = 2 * 60  # 2 minutes.
MAX_TIME_SERIES_PER_CALL = 200

_retry_wrap = {'initial': INITIAL_DELAY_SECONDS,
               'maximum': MAXIMUM_DELAY_SECONDS,
               'deadline': RETRY_DEADLINE_SECONDS}


class _MockMetric(object):
    """Mock metric object, used for when monitoring isn't available."""

    def _mock_method(self, *args, **kwargs):  # pylint: disable=unused-argument
        pass

    def __getattr__(self, _):
        return self._mock_method


class _FlusherThread(threading.Thread):
    """Flusher thread."""

    def __init__(self):
        super(_FlusherThread, self).__init__()
        self.daemon = True
        self.stop_event = threading.Event()

    def run(self):
        """Run the flusher thread."""
        while True:
            try:
                if self.stop_event.wait(FLUSH_INTERVAL_SECONDS):
                    return

                time_series = pd.Series()
                end_time = time.time()
                for metric, labels, start_time, value in _metrics_store.iter_values():
                    if (metric.metric_kind ==
                            'GAUGE'):
                        start_time = end_time

                    series = pd.Series()
                    metric.monitoring_v3_time_series(series, labels, start_time, end_time,
                                                     value)
                    time_series.append(series)

                    if len(time_series) == MAX_TIME_SERIES_PER_CALL:
                        #create_time_series(time_series)
                        time_series = []

               # if time_series:
                    #create_time_series(time_series)
            except Exception:
                logs.log_error('Failed to flush metrics.')

    def stop(self):
        self.stop_event.set()
        self.join()


_StoreValue = collections.namedtuple(
    '_StoreValue', ['metric', 'labels', 'start_time', 'value'])


class _MetricsStore(object):
    """In-process metrics store."""

    def __init__(self):
        self._store = {}
        self._lock = threading.RLock()

    def _get_key(self, metric_name, labels):
        """Get the key used for storing values."""
        if labels:
            normalized_labels = tuple(sorted(six.iteritems(labels)))
        else:
            normalized_labels = None

        return (metric_name, normalized_labels)

    def iter_values(self):
        with self._lock:
            for value in six.itervalues(self._store):
                yield value

    def get(self, metric, labels):
        """Get the stored value for the metric."""
        with self._lock:
            key = self._get_key(metric.name, labels)
            return self._store[key]

    def put(self, metric, labels, value):
        """Store new value for the metric."""
        with self._lock:
            key = self._get_key(metric.name, labels)
            if key in self._store:
                start_time = self._store[key].start_time
            else:
                start_time = time.time()

            self._store[key] = _StoreValue(metric, labels, start_time, value)

    def increment(self, metric, labels, delta):
        """Increment a value by |delta|."""
        with self._lock:
            key = self._get_key(metric.name, labels)

            if key in self._store:
                start_time = self._store[key].start_time
                value = self._store[key].value + delta
            else:
                start_time = time.time()
                value = metric.default_value + delta

            self._store[key] = _StoreValue(metric, labels, start_time, value)

    def reset_for_testing(self):
        """Reset all data. Used for tests."""
        with self._lock:
            self._store.clear()


class _Field(object):
    """_Field is the base class used for field specs."""

    def __init__(self, name):
        self.name = name

    @property
    def value_type(self):
        raise NotImplementedError


class StringField(_Field):
    """StringField spec."""

    @property
    def value_type(self):
        return str


class BooleanField(_Field):
    """BooleanField spec."""

    @property
    def value_type(self):
        return bool


class IntegerField(_Field):
    """IntegerField spec."""

    @property
    def value_type(self):
        return int


class Metric(object):
    """Base metric class."""

    def __init__(self, name, description, field_spec):
        self.name = name
        self.description = description
        self.field_spec = field_spec or []

    @property
    def value_type(self):
        raise NotImplementedError

    @property
    def metric_kind(self):
        raise NotImplementedError

    @property
    def default_value(self):
        raise NotImplementedError

    def _set_value(self, point, value):
        raise NotImplementedError

    def get(self, labels=None):
        """Return the current value for the labels. Used for testing."""
        try:
            return _metrics_store.get(self, labels).value
        except KeyError:
            return self.default_value

    def monitoring_metric(self, metric, labels=None):
        """Get the monitoring_v3 Metric."""
        metric.type = CUSTOM_METRIC_PREFIX + self.name

        if not labels:
            return metric

        for key, value in six.iteritems(labels):
            metric.labels[key] = str(value)

        # Default labels.
        bot_name = environment.get_value('BOT_NAME')
       # metric.labels['region'] = _get_region(bot_name)

        return metric

    def monitoring_metric_descriptor(self, descriptor):
        """Get the monitoring_v3 MetricDescriptor."""
        descriptor.name = self.name
        descriptor.type = CUSTOM_METRIC_PREFIX + self.name
        descriptor.metric_kind = self.metric_kind
        descriptor.value_type = self.value_type
        descriptor.description = self.description

        for field in itertools.chain(DEFAULT_FIELDS, self.field_spec):
            label_descriptor = descriptor.labels.add()
            label_descriptor.key = field.name
            label_descriptor.value_type = field.value_type

        return descriptor

    def monitoring_time_series(self, time_series, labels, start_time, end_time,
                               value):
        """Get the TimeSeries corresponding to the metric."""
        self.monitoring_metric(time_series.metric, labels)
        time_series.resource.CopyFrom(_monitored_resource)
        time_series.metric_kind = self.metric_kind
        time_series.value_type = self.value_type

        point = time_series.points.add()
        _time_to_timestamp(point.interval.start_time, start_time)
        _time_to_timestamp(point.interval.end_time, end_time)
        self._set_value(point.value, value)

        return time_series


class _CounterMetric(Metric):
    """Counter metric."""

    @property
    def value_type(self):
        return CounterMetric.enums.MetricDescriptor.ValueType.INT64

    @property
    def metric_kind(self):
        return 'CUMULATIVE'

    @property
    def default_value(self):
        return 0

    def increment(self, labels=None):
        self.increment_by(1, labels=labels)

    def increment_by(self, count, labels=None):
        _metrics_store.increment(self, labels, count)

    def _set_value(self, point, value):
        """Get Point."""
        point.int64_value = value


class _GaugeMetric(Metric):
    """Gauge metric."""

    @property
    def value_type(self):
        return int

    @property
    def metric_kind(self):
        return 'GAUGE'

    @property
    def default_value(self):
        return 0

    def set(self, value, labels=None):
        _metrics_store.put(self, labels, value)

    def _set_value(self, point, value):
        """Get Point."""
        point.int64_value = value


class _Bucketer(object):
    """Bucketer."""

    def bucket_for_value(self, value):
        """Get the bucket index for the given value."""
        return bisect.bisect(self._lower_bounds, value) - 1

    @property
    def num_buckets(self):
        return len(self._lower_bounds)


class FixedWidthBucketer(_Bucketer):
    """Fixed width bucketer."""

    def __init__(self, width, num_finite_buckets=100):
        self.width = width
        self.num_finite_buckets = num_finite_buckets

        # [-Inf, 0), [0, width), [width, 2*width], ... , [n*width, Inf)
        self._lower_bounds = [float('-Inf')]
        self._lower_bounds.extend(
            [width * i for i in range(num_finite_buckets + 1)])


class GeometricBucketer(_Bucketer):
    """Geometric bucketer."""

    def __init__(self, growth_factor=10 ** 0.2, num_finite_buckets=100, scale=1.0):
        self.growth_factor = growth_factor
        self.num_finite_buckets = num_finite_buckets
        self.scale = scale

        # [-Inf, scale), [scale, scale*growth),
        # [scale*growth^i, scale*growth^(i+1)), ..., [scale*growth^n, Inf)
        self._lower_bounds = [float('-Inf')]
        self._lower_bounds.extend(
            [scale * growth_factor ** i for i in range(num_finite_buckets + 1)])


class _Distribution(object):
    """Holds a distribution."""

    def __init__(self, bucketer):
        self.bucketer = bucketer
        self.buckets = [0 for _ in range(bucketer.num_buckets)]
        self.sum = 0
        self.count = 0

    def add(self, value):
        self.buckets[self.bucketer.bucket_for_value(value)] += 1
        self.count += 1
        self.sum += value
        return self

    __add__ = add

    def monitoring_v3_distribution(self, distribution):
        """Set the monitoring_v3 Distribution value."""
        distribution.count = self.count
        if self.count:
            distribution.mean = float(self.sum) / self.count
        else:
            distribution.mean = 0.0

        if isinstance(self.bucketer, FixedWidthBucketer):
            distribution.bucket_options.linear_buckets.offset = 0
            distribution.bucket_options.linear_buckets.width = self.bucketer.width
            distribution.bucket_options.linear_buckets.num_finite_buckets = (
                self.bucketer.num_finite_buckets)
        else:
            assert isinstance(self.bucketer, GeometricBucketer)

            distribution.bucket_options.exponential_buckets.scale = (
                self.bucketer.scale)
            distribution.bucket_options.exponential_buckets.growth_factor = (
                self.bucketer.growth_factor)
            distribution.bucket_options.exponential_buckets.num_finite_buckets = (
                self.bucketer.num_finite_buckets)

        distribution.bucket_counts.extend(self.buckets)


class _CumulativeDistributionMetric(Metric):
    """Cumulative distribution metric."""

    def __init__(self, name, description, bucketer, field_spec=None):
        super(_CumulativeDistributionMetric, self).__init__(
            name, description=description, field_spec=field_spec)
        self.bucketer = bucketer

    @property
    def value_type(self):
        return 'DISTRIBUTION'

    @property
    def metric_kind(self):
        return 'CUMULATIVE'

    @property
    def default_value(self):
        return _Distribution(self.bucketer)

    def add(self, value, labels=None):
        _metrics_store.increment(self, labels, value)

    def _set_value(self, point, value):
        value.monitoring_v3_distribution(point.distribution_value)


# Global state.
_metrics_store = _MetricsStore()
_monitoring_v3_client = None
_flusher_thread = None
_monitored_resource = None

# Add fields very conservatively here. There is a limit of 10 labels per metric
# descriptor, and metrics should be low in cardinality. That is, only add fields
# which have a small number of possible values.
DEFAULT_FIELDS = [
    StringField('region'),
]


def _time_to_timestamp(timestamp, time_seconds):
    """Convert result of time.time() to Timestamp."""
    timestamp.seconds = int(time_seconds)
    timestamp.nanos = int((time_seconds - timestamp.seconds) * 10 ** 9)


def initialize():
    """Initialize if monitoring is enabled for this bot."""
    global _flusher_thread

    if environment.get_value('LOCAL_DEVELOPMENT'):
        return

    if not os.environ.get('monitoring.enabled'):
        return

    _flusher_thread = _FlusherThread()
    _flusher_thread.start()


def stop():
    """Stops monitoring and cleans up (only if monitoring is enabled)."""
    if _flusher_thread:
        _flusher_thread.stop()


def metrics_store():
    """Get the per-process metrics store."""
    return _metrics_store


def CounterMetric(name, description, field_spec):
    """Build _CounterMetric."""
    return _CounterMetric(name, field_spec=field_spec, description=description)


def GaugeMetric(name, description, field_spec):
    """Build _CounterMetric."""
    return _GaugeMetric(name, field_spec=field_spec, description=description)


def CumulativeDistributionMetric(name, description, bucketer, field_spec):
    """Build _CounterMetric."""
    return _CumulativeDistributionMetric(
        name, description=description, bucketer=bucketer, field_spec=field_spec)