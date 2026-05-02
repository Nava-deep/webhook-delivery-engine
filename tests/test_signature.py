import hmac
from hashlib import sha256

from deliveries.services.signature import generate_signature, render_json_body


def test_hmac_signature_generation_is_correct():
    secret = "endpoint-secret"
    timestamp = "1714650000"
    raw_body = '{"data":{"amount":1999},"id":"evt_1","type":"order.created"}'

    expected = hmac.new(
        secret.encode("utf-8"),
        f"{timestamp}.{raw_body}".encode("utf-8"),
        sha256,
    ).hexdigest()

    assert generate_signature(secret, timestamp, raw_body) == expected


def test_json_body_rendering_is_deterministic():
    body = render_json_body({"type": "order.created", "data": {"b": 2, "a": 1}})

    assert body == '{"data":{"a":1,"b":2},"type":"order.created"}'
