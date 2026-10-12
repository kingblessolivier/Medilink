from unittest.mock import patch

from rest_framework.test import APIClient

from apps.triage.protocol import ProtocolError


def test_invalid_protocol_is_unavailable_not_server_error():
    with patch("apps.triage.views._protocol", side_effect=ProtocolError("invalid protocol")):
        response = APIClient().post("/api/v1/triage/check", {"text": "fever"}, format="json")
    assert response.status_code == 503
    assert response.data["type"] == "service_unavailable"
