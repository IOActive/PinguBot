
"""crash_analyzer tests."""

import os
import unittest

from bot.crash_analysis import crash_analyzer
from bot.tests.test_libs import helpers as test_helpers


class IgnoreStacktraceTest(unittest.TestCase):
  """Tests CrashComparer."""

  def setUp(self):
    test_helpers.patch_environ(self)

  def test_search_excludes(self):
    """Test SEARCH_EXCLUDES env var works."""
    crash_stacktrace = ('aaa\nbbbbbbb\nccc\nddd\n\n')
    self.assertFalse(crash_analyzer.ignore_stacktrace(crash_stacktrace))

    os.environ['SEARCH_EXCLUDES'] = r'eeee'
    self.assertFalse(crash_analyzer.ignore_stacktrace(crash_stacktrace))

    os.environ['SEARCH_EXCLUDES'] = r'ccc'
    self.assertTrue(crash_analyzer.ignore_stacktrace(crash_stacktrace))

  def test_stack_blacklist_regexes(self):
    """Test stacktrace.stack_blacklist_regexes in project.yaml works."""

    def _mock_config_get(_, param):
      """Handle test configuration options."""
      if param == 'stacktrace.stack_blacklist_regexes':
        return [r'.*[c]{3}']
      return None

    test_helpers.patch(
        self, ['bot.config.local_config.ProjectConfig.get'])
    self.mock.get.side_effect = _mock_config_get

    crash_stacktrace = ('aaa\nbbbbbbb\nzzzccc\nddd\n\n')
    self.assertTrue(crash_analyzer.ignore_stacktrace(crash_stacktrace))

    crash_stacktrace = ('aaa\nbbbbbbb\nddd\n\n')
    self.assertFalse(crash_analyzer.ignore_stacktrace(crash_stacktrace))
