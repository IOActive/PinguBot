
"""Tests for compute_engine_projects."""

import unittest

from bot.google_cloud_utils import compute_engine_projects


class LoadProjectTest(unittest.TestCase):
  """Tests load_project."""

  def test_load_test_project(self):
    """Test that test config (project test-clusterfuzz) loads without any
    exceptions."""
    self.assertIsNotNone(
        compute_engine_projects.load_project('test-clusterfuzz'))
