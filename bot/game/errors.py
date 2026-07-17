"""Domain errors shared by the game-state service and HTTP adapter."""

from __future__ import annotations

from typing import Any


class GameStateError(Exception):
    """Base error with a stable API code and an HTTP status."""

    code = "game_state_error"
    status_code = 400

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(message)
        self.message = message
        self.details = details

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"error": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class ValidationError(GameStateError):
    code = "validation_error"
    status_code = 400


class NotFoundError(GameStateError):
    code = "not_found"
    status_code = 404


class ConflictError(GameStateError):
    code = "conflict"
    status_code = 409


class StaleVersionError(ConflictError):
    code = "stale_state_version"

    def __init__(self, expected_version: int, current_version: int) -> None:
        super().__init__(
            "The session changed after the caller's last read.",
            expected_version=expected_version,
            current_version=current_version,
        )
