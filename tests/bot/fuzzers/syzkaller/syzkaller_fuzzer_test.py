
"""Tests for syzkaller engine."""
# pylint: disable=unused-argument

import os
import shutil
import unittest

from bot.tests.test_libs import helpers as test_helpers
from bot.tests.test_libs import test_utils

TEST_PATH = os.path.abspath(os.path.dirname(__file__))
DATA_DIR = os.path.join(TEST_PATH, 'test_data')
TEMP_DIR = os.path.join(TEST_PATH, 'temp')


def clear_temp_dir():
  """Clear temp directory."""
  if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)

  os.mkdir(TEMP_DIR)


@test_utils.integration
class IntegrationTest(unittest.TestCase):
  """Integration tests."""

  def setUp(self):
    test_helpers.patch_environ(self)

    os.environ['BUILD_DIR'] = DATA_DIR
