"""Errors raised by the campaign Director and its public projections."""


class DirectorError(Exception):
    """Base class for Director failures."""


class CampaignValidationError(DirectorError):
    """Raised when campaign source is malformed or internally inconsistent."""


class ProjectionError(DirectorError):
    """Raised when a requested performer projection is invalid or unsafe."""
