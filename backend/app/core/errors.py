"""Domain errors. Messages are user-facing (pt-BR); `code` is stable for the frontend."""


class AppError(Exception):
    status_code = 400
    code = "bad_request"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code:
            self.code = code


class NotFound(AppError):
    status_code = 404
    code = "not_found"


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"


class Forbidden(AppError):
    status_code = 403
    code = "forbidden"


class Conflict(AppError):
    status_code = 409
    code = "conflict"


class RateLimited(AppError):
    status_code = 429
    code = "rate_limited"


class InsufficientCredits(AppError):
    status_code = 402
    code = "insufficient_credits"


class FairUseLimit(AppError):
    status_code = 429
    code = "fair_use_limit"
