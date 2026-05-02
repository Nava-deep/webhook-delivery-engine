import json
import hmac
from datetime import timedelta
from hashlib import sha256

import pytest
from django.core.management import call_command
from django.utils import timezone

from deliveries.models import Delivery
from deliveries.services.delivery import deliver_once


pytestmark = pytest.mark.django_db


class FakeResponse:
    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text


def test_successful_delivery_becomes_delivered(monkeypatch, delivery_factory):
    captured = {}
    delivery = delivery_factory()

    def fake_post(url, content, headers, timeout):
        captured["url"] = url
        captured["content"] = content
        captured["headers"] = headers
        captured["timeout"] = timeout
        return FakeResponse(200, "ok")

    monkeypatch.setattr("deliveries.services.delivery.httpx.post", fake_post)

    result = deliver_once(delivery.id)
    delivery.refresh_from_db()

    sent_body = captured["content"].decode("utf-8")
    sent_payload = json.loads(sent_body)
    timestamp = captured["headers"]["X-Webhook-Timestamp"]
    expected_signature = hmac.new(
        delivery.endpoint.secret.encode("utf-8"),
        f"{timestamp}.{sent_body}".encode("utf-8"),
        sha256,
    ).hexdigest()

    assert result.status == Delivery.Status.DELIVERED
    assert delivery.status == Delivery.Status.DELIVERED
    assert delivery.attempt_count == 1
    assert delivery.last_status_code == 200
    assert delivery.response_body_snippet == "ok"
    assert delivery.next_attempt_at is None
    assert captured["url"] == delivery.endpoint.url
    assert captured["timeout"] == 5
    assert sent_payload["id"] == str(delivery.event_id)
    assert sent_payload["type"] == delivery.event.event_type
    assert sent_payload["data"] == delivery.event.payload
    assert captured["headers"]["X-Webhook-Event-Id"] == str(delivery.event_id)
    assert captured["headers"]["X-Webhook-Delivery-Id"] == str(delivery.id)
    assert captured["headers"]["X-Webhook-Signature"] == expected_signature


def test_failed_delivery_schedules_retry(monkeypatch, delivery_factory):
    delivery = delivery_factory()
    before = timezone.now()

    def fake_post(url, content, headers, timeout):
        return FakeResponse(500, "server error")

    monkeypatch.setattr("deliveries.services.delivery.httpx.post", fake_post)

    deliver_once(delivery.id)
    delivery.refresh_from_db()

    retry_delay = (delivery.next_attempt_at - before).total_seconds()
    assert delivery.status == Delivery.Status.FAILED
    assert delivery.attempt_count == 1
    assert delivery.last_status_code == 500
    assert delivery.last_error == "Non-2xx response: 500"
    assert delivery.response_body_snippet == "server error"
    assert 4 <= retry_delay <= 6


def test_delivery_becomes_dead_lettered_after_max_attempts(
    monkeypatch,
    delivery_factory,
):
    delivery = delivery_factory(attempt_count=4, max_attempts=5)

    def fake_post(url, content, headers, timeout):
        return FakeResponse(500, "still failing")

    monkeypatch.setattr("deliveries.services.delivery.httpx.post", fake_post)

    deliver_once(delivery.id)
    delivery.refresh_from_db()

    assert delivery.status == Delivery.Status.DEAD_LETTERED
    assert delivery.attempt_count == 5
    assert delivery.next_attempt_at is None
    assert delivery.last_status_code == 500


def test_worker_command_processes_due_deliveries(monkeypatch, delivery_factory):
    due_delivery = delivery_factory()

    def fake_post(url, content, headers, timeout):
        return FakeResponse(200, "worker ok")

    monkeypatch.setattr("deliveries.services.delivery.httpx.post", fake_post)

    call_command("run_delivery_worker", "--once", "--poll-interval", "0")

    due_delivery.refresh_from_db()
    assert due_delivery.status == Delivery.Status.DELIVERED
    assert due_delivery.response_body_snippet == "worker ok"


def test_worker_command_can_ignore_schedule_for_demo_runs(
    monkeypatch,
    delivery_factory,
):
    delivery = delivery_factory(
        status=Delivery.Status.FAILED,
        attempt_count=1,
        next_attempt_at=timezone.now() + timedelta(minutes=30),
    )

    def fake_post(url, content, headers, timeout):
        return FakeResponse(200, "forced retry ok")

    monkeypatch.setattr("deliveries.services.delivery.httpx.post", fake_post)

    call_command("run_delivery_worker", "--once", "--ignore-schedule")

    delivery.refresh_from_db()
    assert delivery.status == Delivery.Status.DELIVERED
    assert delivery.response_body_snippet == "forced retry ok"
