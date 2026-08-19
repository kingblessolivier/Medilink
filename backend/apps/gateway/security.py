"""Webhook authentication.

USSD and WhatsApp webhooks carry no user credential: the aggregator is the
caller. They authenticate by shared secret plus source IP, and by HMAC
signature respectively - never by JWT.

**These checks fail closed.** An unauthenticated USSD webhook lets anyone act
as any phone number: read a stranger's queue position, book in their name,
change their insurer. So a missing secret is a refusal, not a bypass - in
development as much as in production. Put a throwaway value in your `.env`.

Keying this off `settings.DEBUG` would be worse than it looks: test runners set
DEBUG to False, and a future deployment that forgets one environment variable
would silently expose the endpoint.
"""

import hashlib
import hmac
import ipaddress
import logging

from django.conf import settings

logger = logging.getLogger(__name__)


class GatewayForbidden(Exception):
    """Rejected webhook.

    A plain exception, not a DRF one: these are plain Django views, so a DRF
    exception would escape the handler and surface as a 500 traceback instead
    of a clean 403.
    """


def client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")


def verify_aggregator(request) -> None:
    """Shared secret plus optional IP allowlist. Raises GatewayForbidden."""
    secret = getattr(settings, "USSD_SHARED_SECRET", "")
    if not secret:
        logger.error("ussd_secret_not_configured")
        raise GatewayForbidden("USSD gateway is not configured.")

    presented = request.headers.get("X-Gateway-Secret", "")
    if not hmac.compare_digest(presented, secret):
        logger.warning("ussd_bad_secret", extra={"ip": client_ip(request)})
        raise GatewayForbidden("Bad gateway credentials.")

    allowlist = getattr(settings, "USSD_ALLOWED_IPS", []) or []
    if allowlist and not _ip_allowed(client_ip(request), allowlist):
        logger.warning("ussd_bad_ip", extra={"ip": client_ip(request)})
        raise GatewayForbidden("Source address not allowed.")


def _ip_allowed(ip: str, allowlist) -> bool:
    try:
        address = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in allowlist:
        try:
            if address in ipaddress.ip_network(entry, strict=False):
                return True
        except ValueError:
            continue
    return False


def verify_whatsapp_signature(request) -> bool:
    """Meta signs every payload with the app secret, over the RAW body.

    Re-serialising the parsed JSON changes whitespace and breaks the
    signature, so this must run against `request.body`.
    """
    app_secret = getattr(settings, "WA_APP_SECRET", "")
    if not app_secret:
        logger.error("whatsapp_secret_not_configured")
        return False

    header = request.headers.get("X-Hub-Signature-256", "")
    if not header.startswith("sha256="):
        return False

    expected = hmac.new(
        app_secret.encode(), request.body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(header.removeprefix("sha256="), expected)
