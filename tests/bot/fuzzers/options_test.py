
"""Tests for libFuzzer."""

import mock
from pyfakefs import fake_filesystem_unittest

from bot.fuzzers.utils import options
from tests.test_libs import test_utils


class FuzzerOptionsTest(fake_filesystem_unittest.TestCase):
    """FuzzerOptions tests."""

    def setUp(self):
        test_utils.set_up_pyfakefs(self)

    @mock.patch('random.SystemRandom')
    def test_basic(self, mock_sysrandom):
        """Basic test."""
        mock_sysrandom.return_value.randint = lambda x, y: 1337

        input_data = ('[libFuzzer]\n'
                      'max_len=9001\n'
                      'dict=blah.dict\n'
                      'blah=9002\n'
                      'rand=random(1, 100)\n'
                      '[asan]\n'
                      'detect_leaks=0\n'
                      '[msan]\n'
                      'msan_option=1\n'
                      '[ubsan]\n'
                      'ubsan_option=0\n')

        self.fs.create_file('/path/blah.options', contents=input_data)
        self.fs.create_file('/path/blah.dict', contents=input_data)
        fuzzer_options = options.FuzzerOptions('/path/blah.options')

        fuzzer_arguments = fuzzer_options.get_engine_arguments('libFuzzer')

        self.assertListEqual(
            sorted(fuzzer_arguments.list()),
            ['-blah=9002', '-dict=/path/blah.dict', '-max_len=9001', '-rand=1337'])
        self.assertDictEqual(
            fuzzer_arguments.dict(), {
                'blah': '9002',
                'dict': '/path/blah.dict',
                'max_len': '9001',
                'rand': '1337'
            })
        self.assertDictEqual(fuzzer_options.get_asan_options(),
                             {'detect_leaks': '0'})
        self.assertDictEqual(fuzzer_options.get_msan_options(),
                             {'msan_option': '1'})
        self.assertDictEqual(fuzzer_options.get_ubsan_options(),
                             {'ubsan_option': '0'})
        self.assertEqual(fuzzer_arguments['max_len'], '9001')
        self.assertEqual(fuzzer_arguments.get('max_len', constructor=int), 9001)
        self.assertEqual(fuzzer_arguments.get('noexist', constructor=int), None)


class GetFuzzTargetOptions(fake_filesystem_unittest.TestCase):
    """get_fuzz_target_options tests."""

    def setUp(self):
        test_utils.set_up_pyfakefs(self)

        input_data = ('[libFuzzer]\nclose_fd_mask=1\n')
        self.fs.create_file('/path/fuzz_target.options', contents=input_data)

    def _get_arguments(self, fuzz_target_path):
        """Helper to return fuzz target arguments by parsing options file for a
    fuzz target."""
        fuzzer_options = options.get_fuzz_target_options(fuzz_target_path)
        if fuzzer_options is None:
            return None

        fuzzer_arguments = fuzzer_options.get_engine_arguments('libFuzzer')
        return sorted(fuzzer_arguments.list())

    def test_without_extension(self):
        self.assertEqual(
            self._get_arguments('/path/fuzz_target'), ['-close_fd_mask=1'])

    def test_with_extension(self):
        self.assertEqual(
            self._get_arguments('/path/fuzz_target.exe'), ['-close_fd_mask=1'])

    def test_not_exist(self):
        self.assertEqual(self._get_arguments('/path/not_exist'), None)
        self.assertEqual(self._get_arguments('/path/not_exist.exe'), None)
