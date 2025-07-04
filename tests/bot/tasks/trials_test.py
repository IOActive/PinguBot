
"""Tests for app specific trials and experiments."""

import unittest

from bot.tasks import trials
from pingu_sdk.system import environment
from tests.test_libs import helpers as test_helpers
from tests.test_libs import test_utils
from pingu_sdk.datastore.models import Trial


class TrialsTest(unittest.TestCase):
  """Tests for trials."""

  def setUp(self):
    test_helpers.patch_environ(self, env={'APP_ARGS': '-x'})
    test_helpers.patch(self,
      [
        'pingu_sdk.datastore.pingu_api.trial_api.TrialApi.get_trials_by_name'
      ]
    )
    
    test_helpers.patch(self, ['random.random'])

  def test_no_effect_on_no_match(self):
    """Ensure that no additional flags are added if a binary has no trials."""
    self.mock.random.return_value = 0.0
    self.mock.get_trials_by_name.return_value = []
    environment.set_value('APP_NAME', 'app_0')
    trial_selector = trials.Trials()
    trial_selector.setup_additional_args_for_app()
    self.assertEqual(environment.get_value('APP_ARGS'), '-x')
    self.assertIsNone(environment.get_value('TRIAL_APP_ARGS'))

  def test_trial_selected_one_option(self):
    """Ensure that the expected flags are added if a trial is selected."""
    self.mock.random.return_value = 0.3
    environment.set_value('APP_NAME', 'app_1')
    self.mock.get_trials_by_name.return_value = [
      Trial(app_name='app_1', probability=0.5, app_args='--a1'),
    ]
    trial_selector = trials.Trials()
    trial_selector.setup_additional_args_for_app()
    self.assertEqual(environment.get_value('APP_ARGS'), '-x --a1')
    self.assertEqual(environment.get_value('TRIAL_APP_ARGS'), '--a1')

  def test_trial_not_selected(self):
    """Ensure no additional flags if a trial was not selected."""
    self.mock.random.return_value = 0.5
    self.mock.get_trials_by_name.return_value = [
      Trial(app_name='app_2', probability=0.4, app_args='--b1'),
      Trial(app_name='app_2', probability=0.2, app_args='--b2'),
    ]
    environment.set_value('APP_NAME', 'app_2')
    trial_selector = trials.Trials()
    trial_selector.setup_additional_args_for_app()
    self.assertEqual(environment.get_value('APP_ARGS'), '-x')
    self.assertIsNone(environment.get_value('TRIAL_APP_ARGS'))

  def test_multiple_trial_selection(self):
    """Ensure that we can suggest the second trial in a batch of multiple."""
    self.mock.random.return_value = 0.1
    self.mock.get_trials_by_name.return_value = [
      Trial(app_name='app_3', probability=1.0, app_args='--c1'),
      Trial(app_name='app_3', probability=0.2, app_args='--c2'),
      Trial(app_name='app_3', probability=0.2, app_args='--c3'),
    ]
    environment.set_value('APP_NAME', 'app_3')
    trial_selector = trials.Trials()
    trial_selector.setup_additional_args_for_app(shuffle=False)
    self.assertEqual(environment.get_value('APP_ARGS'), '-x --c1 --c2 --c3')
    self.assertEqual(environment.get_value('TRIAL_APP_ARGS'), '--c1 --c2 --c3')

  def test_selection_for_windows_executable(self):
    """Ensure that flags are added when the app name ends in ".exe"."""
    self.mock.random.return_value = 0.3
    self.mock.get_trials_by_name.return_value = [
      Trial(app_name='app_1', probability=0.5, app_args='--a1'),
    ]
    environment.set_value('APP_NAME', 'app_1.exe')
    trial_selector = trials.Trials()
    trial_selector.setup_additional_args_for_app()
    self.assertEqual(environment.get_value('APP_ARGS'), '-x --a1')
    self.assertEqual(environment.get_value('TRIAL_APP_ARGS'), '--a1')

  def test_selection_for_android_apk(self):
    """Ensure that flags are added for the Android APK format."""
    self.mock.random.return_value = 0.3
    self.mock.get_trials_by_name.return_value = [
      Trial(app_name='app_1', probability=0.5, app_args='--a1'),
    ]
    environment.set_value('APP_NAME', 'App_1.apk')
    trial_selector = trials.Trials()
    trial_selector.setup_additional_args_for_app()
    self.assertEqual(environment.get_value('APP_ARGS'), '-x --a1')
    self.assertEqual(environment.get_value('TRIAL_APP_ARGS'), '--a1')
