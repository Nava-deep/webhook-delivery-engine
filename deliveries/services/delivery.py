import time
from typing import Any

import httpx
from django.db import transaction
from django.utils import timezone

from deliveries.models import Delivery
from deliveries.services.retry import retry_delay_for_attempt
from deliveries.services.signature import generate_signature, render_json_body


DELIVERY_TIMEOUT_SECONDS = 5
RESPONSE_SNIPPET_LENGTH = 500


def build_webhook_payload(delivery: Delivery) -> dict[str, Any]:
    event = delivery.event
    return {
        "id": str(event.id),
        "type": event.event_type,
        "created_at": event.created_at.isoformat(),
        "data": event.payload,
    }


def build_delivery_headers(delivery: Delivery, timestamp: str, raw_body: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Webhook-Event-Id": str(delivery.event_id),
        "X-Webhook-Delivery-Id": str(delivery.id),
        "X-Webhook-Timestamp": timestamp,
        "X-Webhook-Signature": generate_signature(
            delivery.endpoint.secret,
            timestamp,
            raw_body,
        ),
    }


def deliver_once(delivery_id) -> Delivery:
    delivery = Delivery.objects.select_related("event", "endpoint").get(id=delivery_id)

    with transaction.atomic():
        claimed = Delivery.objects.filter(
            id=delivery.id,
            status__in=[Delivery.Status.PENDING, Delivery.Status.FAILED],
            attempt_count__lt=delivery.max_attempts,
        ).update(
            status=Delivery.Status.DELIVERING,
            last_attempt_at=timezone.now(),
        )
        if not claimed:
            return Delivery.objects.select_related("event", "endpoint").get(id=delivery.id)

    delivery = Delivery.objects.select_related("event", "endpoint").get(id=delivery.id)
    payload = build_webhook_payload(delivery)
    raw_body = render_json_body(payload)
    timestamp = str(int(time.time()))
    headers = build_delivery_headers(delivery, timestamp, raw_body)

    try:
        response = httpx.post(
            delivery.endpoint.url,
            content=raw_body.encode("utf-8"),
            headers=headers,
            timeout=DELIVERY_TIMEOUT_SECONDS,
        )
    except httpx.TimeoutException:
        return record_failure(delivery, error="Request timed out")
    except httpx.HTTPError as exc:
        return record_failure(delivery, error=str(exc))

    snippet = response.text[:RESPONSE_SNIPPET_LENGTH]
    if 200 <= response.status_code < 300:
        return record_success(delivery, response.status_code, snippet)

    return record_failure(
        delivery,
        status_code=response.status_code,
        error=f"Non-2xx response: {response.status_code}",
        response_snippet=snippet,
    )


def record_success(delivery: Delivery, status_code: int, response_snippet: str) -> Delivery:
    delivery.attempt_count += 1
    delivery.status = Delivery.Status.DELIVERED
    delivery.last_status_code = status_code
    delivery.last_error = ""
    delivery.response_body_snippet = response_snippet
    delivery.next_attempt_at = None
    delivery.save(
        update_fields=[
            "attempt_count",
            "status",
            "last_status_code",
            "last_error",
            "response_body_snippet",
            "next_attempt_at",
            "updated_at",
        ]
    )
    return delivery


def record_failure(
    delivery: Delivery,
    *,
    error: str,
    status_code: int | None = None,
    response_snippet: str = "",
) -> Delivery:
    delivery.attempt_count += 1
    delivery.last_status_code = status_code
    delivery.last_error = error[:1000]
    delivery.response_body_snippet = response_snippet[:RESPONSE_SNIPPET_LENGTH]

    if delivery.attempt_count >= delivery.max_attempts:
        delivery.status = Delivery.Status.DEAD_LETTERED
        delivery.next_attempt_at = None
    else:
        delivery.status = Delivery.Status.FAILED
        delivery.next_attempt_at = timezone.now() + retry_delay_for_attempt(
            delivery.attempt_count
        )

    delivery.save(
        update_fields=[
            "attempt_count",
            "last_status_code",
            "last_error",
            "response_body_snippet",
            "status",
            "next_attempt_at",
            "updated_at",
        ]
    )
    return delivery
