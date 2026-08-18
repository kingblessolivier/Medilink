"""RFC-7807-style error bodies, as specified in docs/03-api-specification.md."""

from rest_framework.views import exception_handler as drf_exception_handler

_TYPE_BY_STATUS = {
    400: "validation_error",
    401: "authentication_required",
    403: "permission_denied",
    404: "not_found",
    409: "conflict",
    429: "rate_limited",
    503: "service_unavailable",
}


def rfc7807_exception_handler(exc, context):
    response = drf_exception_handler(exc, context)
    if response is None:
        return None

    error_type = _TYPE_BY_STATUS.get(response.status_code, "error")
    detail, field = _flatten(response.data)

    body = {"type": error_type, "detail": detail}
    if field:
        body["field"] = field
    response.data = body
    return response


def _flatten(data):
    """Reduce the nested DRF error structure to a (detail, field) pair."""
    if isinstance(data, dict):
        if "detail" in data:
            return str(data["detail"]), None
        for field, messages in data.items():
            if isinstance(messages, list) and messages:
                return str(messages[0]), field
            return str(messages), field
    if isinstance(data, list) and data:
        return str(data[0]), None
    return str(data), None
