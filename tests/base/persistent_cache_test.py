
"""Tests for persistent_cache."""

import datetime

from pyfakefs import fake_filesystem_unittest

from bot.system import environment, persistent_cache
from tests.test_libs import test_utils
from tests.test_libs import helpers as test_helpers


class PersistentCacheTest(fake_filesystem_unittest.TestCase):
    """Tests for persistent_cache functions."""

    def setUp(self):
        test_helpers.patch_environ(self)
        test_utils.set_up_pyfakefs(self)
        environment.set_value('CACHE_DIR', '/tmp/test-cache')
        persistent_cache.initialize()

    def test_set_get_string(self):
        """Ensure it works with string value."""
        persistent_cache.set_value('key', 'value')
        self.assertEqual(persistent_cache.get_value('key'), 'value')

    def test_set_get_datetime(self):
        """Ensure it works with datetime value."""
        epoch = datetime.datetime.utcfromtimestamp(0)
        end_time = datetime.datetime.utcfromtimestamp(10)
        diff_time = end_time - epoch
        persistent_cache.set_value('key', diff_time.total_seconds())
        self.assertEqual(
            persistent_cache.get_value(
                'key', constructor=datetime.datetime.utcfromtimestamp), end_time)

    def test_delete(self):
        """Ensure it deletes key."""
        persistent_cache.set_value('key', 'value')
        persistent_cache.delete_value('key')
        self.assertEqual(persistent_cache.get_value('key'), None)

    def test_get_nonexistence(self):
        """Ensure it returns default_value when key doesn't exists."""
        self.assertEqual(persistent_cache.get_value('key', default_value=1), 1)

    def test_get_invalid(self):
        """Ensure it returns default_value when constructor fails."""
        time_now = datetime.datetime.utcnow()
        persistent_cache.set_value('key', 'random')
        self.assertEqual(persistent_cache.get_value('key'), 'random')
        self.assertEqual(
            persistent_cache.get_value(
                'key',
                default_value=time_now,
                constructor=datetime.datetime.utcfromtimestamp), time_now)

    def test_persist_across_reboots(self):
        """Ensure persist_across_reboots works."""
        persistent_cache.set_value('key', 'a')
        persistent_cache.set_value('key2', 'b', persist_across_reboots=True)
        persistent_cache.clear_values()
        self.assertEqual(persistent_cache.get_value('key'), None)
        self.assertEqual(persistent_cache.get_value('key2'), 'b')

    def test_clear_all(self):
        """Ensure clear all works."""
        persistent_cache.set_value('key', 'a')
        persistent_cache.set_value('key2', 'b', persist_across_reboots=True)
        persistent_cache.clear_values(clear_all=True)
        self.assertEqual(persistent_cache.get_value('key'), None)
        self.assertEqual(persistent_cache.get_value('key2'), None)
