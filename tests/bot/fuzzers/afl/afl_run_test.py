
"""Tests for fuzzer.py."""

import os

from bot.fuzzers.afl import fuzzer
from bot.tests.core.bot.fuzzers import builtin_test
from bot.tests.test_libs import helpers


class FuzzerTest(builtin_test.BaseEngineFuzzerTest):
  """Unit tests for fuzzer."""

  def setUp(self):
    super(FuzzerTest, self).setUp()
    helpers.patch(self, [
        'bot.metrics.logs.log_warn',
    ])

  def _test_passed(self):
    self.assertTrue(os.path.exists('/output/fuzz-0'))
    self.assertTrue(os.path.exists('/output/flags-0'))
    self.assertTrue(os.path.exists('/input/proj_target/in1'))

    with open('/output/flags-0') as f:
      self.assertEqual('%TESTCASE% target', f.read())

  def _test_failed(self):
    self.assertFalse(os.path.exists('/output/fuzz-0'))
    self.assertFalse(os.path.exists('/output/flags-0'))
    self.assertFalse(os.path.exists('/input/proj_target/in1'))

  def test_run(self):
    """Test running afl fuzzer."""
    afl = fuzzer.Afl()
    afl.run('/input', '/output', 1)

    self._test_passed()
