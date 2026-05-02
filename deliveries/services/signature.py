import hmac
import json
from hashlib import sha256


def render_json_body(payload: dict) -> str:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def generate_signature(secret: str, timestamp: str, raw_json_body: str) -> str:
    signing_string = f"{timestamp}.{raw_json_body}"
    return hmac.new(
        secret.encode("utf-8"),
        signing_string.encode("utf-8"),
        sha256,
    ).hexdigest()
