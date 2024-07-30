
"""Exception classes for minimizers."""


class MinimizationDeadlineExceededError(Exception):
    """Exception thrown if the deadline for minimization has been exceeded."""

    def __init__(self, testcase):
        Exception.__init__(self, 'Deadline exceeded.')
        self.testcase = testcase


class NoCommandError(Exception):
    """Exception thrown if no command is configured for test runs."""

    def __init__(self):
        Exception.__init__(self, 'Attempting to run with no command configured.')


class TokenizationFailureError(Exception):

    def __init__(self, minimization_type):
        Exception.__init__(self, 'Unable to perform ' + minimization_type + '.')


class AntlrDecodeError(Exception):
    """Raised when Antlr can't minimize input because it is not unicode."""
