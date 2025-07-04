
"""Helper functions for app-specific trials/experiments."""

import json
import os
import random

from pingu_sdk.system import environment
from pingu_sdk.utils import utils
from pingu_sdk.datastore.pingu_api.pingu_api_client import get_api_client
from pingu_sdk.metrics import logs

TRIALS_CONFIG_FILENAME = 'trials_config.json'


class AppArgs:

  def __init__(self, probability):
    self.probability = probability

class Trials:
    """Helper class for selecting app-specific extra flags."""

    def __init__(self):
        self.trials = {}

        app_name = environment.get_value('APP_NAME')
        if not app_name:
            return

        # Convert the app_name to lowercase. Case may vary by platform.
        app_name = app_name.lower()

        # Hack: strip file extensions that may be appended on various platforms.
        extensions_to_strip = ['.exe', '.apk']
        for extension in extensions_to_strip:
            app_name = utils.strip_from_right(app_name, extension)

        for trial in get_api_client().trial_api.get_trials_by_name(app_name):
            self.trials[trial.app_args] = AppArgs(trial.probability)

        app_dir = environment.get_value('APP_DIR')
        if not app_dir:
            return

        trials_config_path = os.path.join(app_dir, TRIALS_CONFIG_FILENAME)
        if not os.path.exists(trials_config_path):
            return

        try:
            with open(trials_config_path) as json_file:
                trials_config = json.load(json_file)
                for config in trials_config:
                    if config['app_name'] != app_name:
                        continue
                    self.trials[config['app_args']] = AppArgs(config['probability'])
        except Exception as e:
            logs.log_warn('Unable to parse config file: %s' % str(e))
        return

    def setup_additional_args_for_app(self, shuffle=True):
        """Select additional args for the specified app at random."""
        trial_args = []

        trial_keys = list(self.trials)

        if shuffle:
            random.shuffle(trial_keys)

        for app_args in trial_keys:
            if random.random() < self.trials[app_args].probability:
                trial_args.append(app_args)
        if not trial_args:
            return

        trial_app_args = ' '.join(trial_args)
        app_args = environment.get_value('APP_ARGS', '')
        environment.set_value('APP_ARGS', '%s %s' % (app_args, trial_app_args))
        environment.set_value('TRIAL_APP_ARGS', trial_app_args)
