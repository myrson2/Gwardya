"""Domain errors mapped to HTTP by a single handler in ``app.main``.

Services raise these instead of ``HTTPException`` so business rules stay transport
agnostic (tech-stack §Layer boundaries).
"""


class AppError(Exception):
    status_code = 400
    clear_refresh_cookie = False

    def __init__(self, detail: str) -> None:
        super().__init__(detail)
        self.detail = detail


class UnauthorizedError(AppError):
    status_code = 401


class ForbiddenError(AppError):
    status_code = 403


class NotFoundError(AppError):
    status_code = 404


class ConflictError(AppError):
    status_code = 409


class SetupError(AppError):
    """The database is missing prerequisites (normally: seed not run)."""

    status_code = 503


class RefreshReuseError(UnauthorizedError):
    """A rotated refresh token was presented again; the chain is now revoked."""

    clear_refresh_cookie = True
