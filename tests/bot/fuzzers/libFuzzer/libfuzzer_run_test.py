
"""Tests for fuzzer.py."""

import os
import unittest

from bot.fuzzers.libFuzzer import fuzzer
from bot.system import environment
from bot.tests.core.bot.fuzzers import builtin_test
from bot.tests.test_libs import helpers as test_helpers

SCRIPT_DIR = os.path.abspath(os.path.dirname(__file__))


class GenerateArgumentsTests(unittest.TestCase):
  """Unit tests for fuzzer.py."""

  def setUp(self):
    """Set up test environment."""
    test_helpers.patch_environ(self)
    environment.set_value('FUZZ_TEST_TIMEOUT', '4800')

    self.build_dir = os.path.join(SCRIPT_DIR, 'run_data', 'build_dir')
    self.corpus_directory = 'data/corpus_with_some_files'

  def test_generate_arguments_default(self):
    """Test generateArgumentsForFuzzer."""
    fuzzer_path = os.path.join(self.build_dir, 'fake0_fuzzer')
    libfuzzer = fuzzer.LibFuzzer()
    arguments = libfuzzer.generate_arguments(fuzzer_path)
    expected_arguments = '-timeout=25 -rss_limit_mb=2560'

    self.assertEqual(arguments, expected_arguments)

  def test_generate_arguments_with_options_file(self):
    """Test generateArgumentsForFuzzer."""
    fuzzer_path = os.path.join(self.build_dir, 'fake1_fuzzer')
    libfuzzer = fuzzer.LibFuzzer()
    arguments = libfuzzer.generate_arguments(fuzzer_path)

    expected_arguments = (
        '-max_len=31337 -timeout=11 -runs=9999999 -rss_limit_mb=2560')
    self.assertEqual(arguments, expected_arguments)


class FuzzerTest(builtin_test.BaseEngineFuzzerTest):
  """Unit tests for fuzzer."""

  def test_run(self):
    """Test running libFuzzer fuzzer."""
    libfuzzer = fuzzer.LibFuzzer()
    libfuzzer.run('/input', '/output', 1)
    with open('/output/flags-0') as f:
      self.assertEqual('%TESTCASE% target -timeout=25 -rss_limit_mb=2560',
                       f.read())
