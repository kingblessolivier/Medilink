"""Inbound webhooks.

Both endpoints must answer fast and must never return a bare 500. The
aggregator gives us a couple of seconds; Meta retries with backoff on any
non-200, producing duplicate messages.
"""

import json
import logging

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods, require_POST

from apps.patients.models import normalise_phone

from . import strings as S
from .security import (
    GatewayForbidden,
    verify_aggregator,
    verify_whatsapp_signature,
)
from .ussd import UssdRouter, end
from .whatsapp import handle_inbound_message

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def ussd(request):
    """Africa's Talking style: form-encoded in, plain text out.

    `CON ` keeps the session open, `END ` closes it.
    """
    try:
        verify_aggregator(request)
    except GatewayForbidden as exc:
        # A clean 403, never a 500 traceback: the aggregator logs our status
        # code and we do not want a stack trace in their dashboard.
        return HttpResponseForbidden(str(exc))

    session_id = request.POST.get("sessionId", "")
    raw_phone = request.POST.get("phoneNumber", "")
    text = request.POST.get("text", "")

    try:
        phone = normalise_phone(raw_phone)
    except Exception:  # noqa: BLE001
        logger.warning("ussd_bad_phone", extra={"session": session_id})
        return _plain(end(S.t(S.SERVICE_UNAVAILABLE, "rw")))

    try:
        reply = UssdRouter(session_id=session_id, phone=phone).handle(text)
    except Exception:  # noqa: BLE001
        # The bare except is deliberate here and nowhere else in the codebase.
        # A traceback reaching the aggregator shows the patient a blank screen
        # with no explanation and no way forward.
        logger.exception("ussd_failure", extra={"session": session_id})
        reply = end(S.t(S.SERVICE_UNAVAILABLE, "rw"))

    return _plain(reply)


def _plain(body: str) -> HttpResponse:
    return HttpResponse(body, content_type="text/plain; charset=utf-8")


@csrf_exempt
@require_http_methods(["GET", "POST"])
def whatsapp(request):
    if request.method == "GET":
        # Meta's one-time subscription handshake.
        token = request.GET.get("hub.verify_token")
        expected = getattr(settings, "WA_VERIFY_TOKEN", "")
        if expected and token == expected:
            return HttpResponse(request.GET.get("hub.challenge", ""))
        return HttpResponseForbidden("bad verify token")

    if not verify_whatsapp_signature(request):
        logger.warning("whatsapp_bad_signature")
        return HttpResponseForbidden("bad signature")

    try:
        payload = json.loads(request.body or b"{}")
    except ValueError:
        logger.warning("whatsapp_bad_json")
        return JsonResponse({"ok": True})  # never make Meta retry bad JSON

    try:
        handle_inbound_message(payload)
    except Exception:  # noqa: BLE001
        # Answer 200 regardless: a non-200 makes Meta redeliver, and the
        # patient receives the same reply several times.
        logger.exception("whatsapp_handler_failed")

    return JsonResponse({"ok": True})
