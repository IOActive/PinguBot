
"""Helper functions for app-specific trials/experiments."""

import random

from bot.datastore import data_handler
from bot.datastore import data_types
from bot.system import environment
from bot.utils import utils


class Trials:
    """Helper class for selecting app-specific extra flags."""

    def __init__(self):
        self.trials = []

        app_name = environment.get_value('APP_NAME')
        if not app_name:
            return

        # Convert the app_name to lowercase. Case may vary by platform.
        app_name = app_name.lower()

        # Hack: strip file extensions that may be appended on various platforms.
        extensions_to_strip = ['.exe', '.apk']
        for extension in extensions_to_strip:
            app_name = utils.strip_from_right(app_name, extension)

        self.trials = data_handler.get_trial_by_appname(app_name)

    def setup_additional_args_for_app(self):
        """Select additional args for the specified app at random."""
        trial_args = [
            trial.app_args
            for trial in self.trials
            if random.random() < trial.probability
        ]
        if not trial_args:
            return

        trial_app_args = ' '.join(trial_args)
        app_args = environment.get_value('APP_ARGS', '')
        environment.set_value('APP_ARGS', '%s %s' % (app_args, trial_app_args))
        environment.set_value('TRIAL_APP_ARGS', trial_app_args)
