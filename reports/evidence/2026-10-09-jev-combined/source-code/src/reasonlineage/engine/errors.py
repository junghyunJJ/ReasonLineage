"""Errors that end a run cleanly, each with a message that says what to do next."""


class RunStopped(RuntimeError):
    """The run cannot continue in this mode. Fix the cause, then `reasonlineage resume`."""


class ResumeMismatch(RuntimeError):
    """Re-running the recorded calls did not reproduce the recorded decisions."""


class RunCorrupted(RuntimeError):
    """The run folder is missing a file that its event log refers to."""
