from flask import jsonify


class BaseError(Exception):

    def __init__(self, message=None, status_code=500):
        self.message = message or "Internal server error"
        self.status_code = status_code

    def to_response(self) -> tuple:
        return jsonify({"error": self.message}), self.status_code


class ServiceUnavailableError(BaseError):
    status_code = 503

    def __init__(self, message=None):
        message = message or "Service unavailable"
        super().__init__(message=message, status_code=self.status_code)


class BadRequestError(BaseError):
    status_code = 400

    def __init__(self, message=None):
        message = message or "Bad request"
        super().__init__(message=message, status_code=self.status_code)


def handle_error(error: Exception, message: str = None) -> tuple:

    # Handle custom errors
    if isinstance(error, BaseError):
        return error.to_response()

    # Default fallback response
    return BaseError().to_response()