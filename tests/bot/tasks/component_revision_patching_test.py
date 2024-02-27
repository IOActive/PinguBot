
"""Test base class for tasks which involve looking into component revisions."""

import ast
import os
import unittest

from bot.tests.test_libs import helpers
from bot.tests.test_libs import test_utils

DATA_DIRECTORY = os.path.join(
    os.path.dirname(__file__), 'component_related_test_data')


@test_utils.with_cloud_emulators('datastore')
class ComponentRevisionPatchingTest(unittest.TestCase):
  """Base class for tests involving revisions of components;
  patches the function which retrieves those revisions."""

  def setUp(self):
    helpers.patch_environ(self)

    helpers.patch(self, [
        'bot.build_management.revisions.get_component_revisions_dict',
    ])

    self.mock.get_component_revisions_dict.side_effect = (
        self.mock_get_component_revisions_dict)

  @staticmethod
  def mock_get_component_revisions_dict(revision, _):
    if revision == 0:
      return {}

    component_revisions_file_path = os.path.join(
        DATA_DIRECTORY, 'component_revisions_%s.txt' % revision)
    with open(component_revisions_file_path) as file_handle:
      return ast.literal_eval(file_handle.read())
