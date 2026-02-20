"""Custom exception classes for the application."""


class AppException(Exception):
    """Base exception for the application."""

    def __init__(self, message: str, code: str = "APP_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)


class NotFoundError(AppException):
    """Resource not found."""

    def __init__(self, resource: str, identifier: str):
        super().__init__(
            message=f"{resource} with id '{identifier}' not found",
            code="NOT_FOUND",
        )


class ValidationError(AppException):
    """Validation error."""

    def __init__(self, message: str):
        super().__init__(message=message, code="VALIDATION_ERROR")


class AuthenticationError(AppException):
    """Authentication failed."""

    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message=message, code="AUTH_ERROR")


class EscalationRequired(AppException):
    """Escalation to human agent required."""

    def __init__(self, reason: str, urgency: str = "normal"):
        self.reason = reason
        self.urgency = urgency
        super().__init__(
            message=f"Escalation required: {reason}",
            code="ESCALATION_REQUIRED",
        )
