"""Triage endpoints.

Every one of these returns **503** until a clinician sign-off is configured.
That is not a placeholder - it is the feature working correctly. See gate.py.
"""

import logging

from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status as http
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import engine
from .gate import TriageUnavailable, approval, require_approval
from .models import TriageOutcome
from .protocol import ProtocolError, load
from .serializers import (
    AnswerSerializer,
    TriageSessionSerializer,
    TriageStatusSerializer,
)

logger = logging.getLogger(__name__)


def _unavailable(exc) -> Response:
    return Response(
        {"type": "service_unavailable", "detail": str(exc)},
        status=http.HTTP_503_SERVICE_UNAVAILABLE,
    )


def _protocol():
    record = require_approval()
    return load(record.protocol_file), record


def _render(protocol, state, record) -> dict:
    """Shape the client sees.

    The disclaimer is on EVERY response, not shown once at onboarding: a
    patient who joins mid-flow, or returns later, must still see it.
    """
    question = engine.next_question(protocol, state)

    payload = {
        "session_id": state.session_id,
        "protocol_version": protocol.version,
        "approved_by": record.approved_by,
        "disclaimer": protocol.disclaimer,
        "escalate_emergency": state.escalated,
        "emergency_advice": protocol.emergency_advice if state.escalated else None,
        "recommendation": state.recommendation or None,
        "finished": state.finished,
        "next_question": None,
    }

    if question is not None:
        payload["next_question"] = {
            "code": question.code,
            "red_flag": question.red_flag,
            "text": question.text,
            "options": [
                {"code": option.code, "text": option.text}
                for option in question.options
            ],
        }

    return payload


def _record_outcome(protocol, state) -> None:
    """Persist an anonymous aggregate only - never the answers."""
    now = timezone.localtime()
    TriageOutcome.objects.create(
        protocol_version=protocol.version,
        recommended_service=state.recommendation,
        escalated_emergency=state.escalated,
        questions_answered=len(state.asked),
        date=now.date(),
        hour_bucket=now.hour,
    )


@extend_schema(
    summary="Whether the symptom checker is available",
    description=(
        "Reports whether a clinician sign-off has been recorded. The client "
        "must hide the symptom checker entirely when this returns "
        "available=false, rather than showing a broken entry point."
    ),
    responses=TriageStatusSerializer,
)
@api_view(["GET"])
@permission_classes([AllowAny])
def status_view(request):
    record = approval()
    return Response(
        {
            "available": record is not None,
            "protocol_version": record.protocol_version if record else "",
            "approved_by": record.approved_by if record else "",
            "approved_on": record.approved_on if record else "",
            "reason": (
                ""
                if record
                else "Awaiting review and sign-off by a licensed clinician."
            ),
        }
    )



@extend_schema(
    summary="Start a triage session",
    request=None,  # no body; the first question comes back in the response
    responses=TriageSessionSerializer,
)
@api_view(["POST"])
@permission_classes([AllowAny])
def create_session(request):
    try:
        protocol, record = _protocol()
    except TriageUnavailable as exc:
        return _unavailable(exc)
    except ProtocolError as exc:
        # A malformed protocol is never served on a best-effort basis.
        logger.exception("triage_protocol_invalid")
        return _unavailable(f"Symptom checker misconfigured: {exc}")

    state = engine.new_session(protocol)
    return Response(_render(protocol, state, record), status=http.HTTP_201_CREATED)


@extend_schema(
    summary="Answer the current question",
    request=AnswerSerializer,
    responses=TriageSessionSerializer,
)
@api_view(["POST"])
@permission_classes([AllowAny])
def answer_question(request, session_id):
    try:
        protocol, record = _protocol()
    except TriageUnavailable as exc:
        return _unavailable(exc)
    except ProtocolError as exc:
        logger.exception("triage_protocol_invalid")
        return _unavailable(f"Symptom checker misconfigured: {exc}")

    payload = AnswerSerializer(data=request.data)
    payload.is_valid(raise_exception=True)

    try:
        state = engine.load_session(session_id)
        state = engine.answer(
            protocol,
            state,
            payload.validated_data["question"],
            payload.validated_data["option"],
        )
    except engine.TriageError as exc:
        return Response(
            {"type": "validation_error", "detail": str(exc)},
            status=http.HTTP_400_BAD_REQUEST,
        )

    body = _render(protocol, state, record)

    if state.finished:
        _record_outcome(protocol, state)
        # Answers are discarded the moment the flow ends.
        engine.discard(state.session_id)

    return Response(body)
