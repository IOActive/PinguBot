
"""Functions for errors management."""

# Phrases to look in an error stacktrace to determine if something bad happened
# which is non recoverable and we just want to hang in that situation without
# proceeding further. This also helps to later come up and debug the problem.
BOT_ERROR_HANG_LIST = ['no space left']

# Phrases to look in an error stacktrace to determine whether the bot should
# terminate or not.
BOT_ERROR_TERMINATION_LIST = [
    'can\'t start new thread',
    'cannot allocate memory',
    'hostexception',
    'interrupted function call',
    'out of memory',
    'systemexit:',
]


def error_in_list(error_stacktrace, error_list):
    """Returns if the error exists in the error list."""
    # Change all strings to lowercase for comparison.
    error_stacktrace = error_stacktrace.lower()
    error_list = [error.lower() for error in error_list]

    for error in error_list:
        if error in error_stacktrace:
            return True

    return False


class Error(Exception):
    """Base exception class for errors."""


class InvalidTestcaseError(Error):
    """Error thrown when there is an attempt to access an invalid test case."""

    def __init__(self):
        super().__init__('Invalid test case.')


class InvalidFuzzerError(Error):
    """Error thrown when there is an attempt to set up a nonexistent fuzzer."""

    def __init__(self):
        super().__init__('Invalid fuzzer.')


class BadStateError(Error):
    """We are in an unexpected state that we cannot recover from."""

    def __init__(self, message=None):
        super().__init__('Entered a bad state.' or message)


class BuildNotFoundError(Error):
    """Exception type for build not found failures."""

    def __init__(self, revision, job_type):
        self.revision = revision
        self.job_type = job_type
        super().__init__()

    def __str__(self):
        return 'Build not found (revision %d, job %s).' % (self.revision,
                                                           self.job_type)


class BuildSetupError(Error):
    """Exception type for build setup failures."""

    def __init__(self, revision, job_type):
        self.revision = revision
        self.job_type = job_type
        super().__init__()

    def __str__(self):
        return 'Build setup failed (revision %d, job %s).' % (self.revision,
                                                              self.job_type)


class BadBuildError(Error):
    """Exception type for bad build failures."""

    def __init__(self, revision, job_type):
        self.revision = revision
        self.job_type = job_type
        super().__init__()

    def __str__(self):
        return 'Bad build detected (revision %d, job %s).' % (self.revision,
                                                              self.job_type)


class BadConfigError(Error):
    """Error thrown when configuration is bad."""

    def __init__(self, config_dir):
        super().__init__(
            'Bad configuration at: {config_dir}'.format(config_dir=config_dir))


class ConfigParseError(Error):
    """Error thrown when we failed to parse a config yaml file."""

    def __init__(self, file_path):
        self.file_path = file_path
        super().__init__()

    def __str__(self):
        return 'Failed to parse config file %s.' % self.file_path


class InvalidConfigKey(Error):
    """Error thrown when we failed to parse a config yaml file."""

    def __init__(self, key_name):
        self.key_name = key_name
        super().__init__()

    def __str__(self):
        return 'Invalid config key %s.' % self.key_name
