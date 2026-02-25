"""Exceptions for the BuildingLink API client."""


class BuildingLinkError(Exception):
    """Base exception for BuildingLink errors."""


class AuthenticationError(BuildingLinkError):
    """Raised when authentication fails."""


class TokenExpiredError(AuthenticationError):
    """Raised when the access token has expired and refresh fails."""


class APIError(BuildingLinkError):
    """Raised when an API request fails."""

    def __init__(self, status: int, message: str) -> None:
        self.status = status
        super().__init__(f"API error {status}: {message}")
