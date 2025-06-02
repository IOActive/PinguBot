
"""Run tests."""
import unittest

import mock

from tests.test_libs import helpers
from bot.startup import run


class RunLoopTest(unittest.TestCase):
  """Test run_loop."""

  def setUp(self):
    helpers.patch(self, [
        'atexit.register',
        'bot.startup.run.start_bot',
        'bot.startup.run.start_heartbeat',
        'bot.startup.run.stop_heartbeat',
        'bot.startup.run.sleep',
        'pingu_sdk.datastore.data_handler.bot_run_timed_out',
    ])

  def test_loop(self):
    """Test looping until break."""
    self.mock.bot_run_timed_out.side_effect = [False, False, True]
    self.mock.start_bot.return_value = 1

    run.run_loop('working_directory command', 'heartbeat command')

    self.assertEqual(3, self.mock.start_heartbeat.call_count)
    self.assertEqual(1, self.mock.register.call_count)
    self.assertEqual(0, self.mock.stop_heartbeat.call_count)  # Handled at exit.
    self.assertEqual(3, self.mock.start_bot.call_count)
    self.assertEqual(3, self.mock.bot_run_timed_out.call_count)

    self.mock.start_bot.assert_has_calls([
        mock.call('working_directory command'),
        mock.call('working_directory command'),
        mock.call('working_directory command'),
    ])
