"""Domain exceptions for lsh."""


class LshError(Exception):
    """Base exception for lsh failures."""


class ValidationError(LshError):
    """Raised when a plan fails validation."""


class ExecutionError(LshError):
    """Raised when a step cannot be executed."""
