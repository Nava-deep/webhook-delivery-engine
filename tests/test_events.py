import pytest

from deliveries.models import Delivery, Event


pytestmark = pytest.mark.django_db


def test_event_publish_creates_deliveries_for_matching_endpoints(
    api_client,
    endpoint_factory,
):
    matching = endpoint_factory(
        url="http://receiver-a.test/webhook",
        event_types=["order.created", "payment.succeeded"],
    )
    non_matching = endpoint_factory(
        url="http://receiver-b.test/webhook",
        event_types=["invoice.failed"],
    )

    response = api_client.post(
        "/api/events/",
        {
            "event_type": "order.created",
            "payload": {"order_id": "ord_123", "amount": 1999},
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["deliveries_created"] == 1

    event = Event.objects.get()
    delivery = Delivery.objects.get(event=event)
    assert delivery.endpoint == matching
    assert delivery.endpoint != non_matching
    assert delivery.status == Delivery.Status.PENDING


def test_event_publish_does_not_create_deliveries_for_non_matching_event_types(
    api_client,
    endpoint_factory,
):
    endpoint_factory(event_types=["payment.succeeded"])

    response = api_client.post(
        "/api/events/",
        {
            "event_type": "order.created",
            "payload": {"order_id": "ord_123"},
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["deliveries_created"] == 0
    assert Event.objects.count() == 1
    assert Delivery.objects.count() == 0


def test_idempotency_key_prevents_duplicate_event_creation(api_client, endpoint_factory):
    endpoint_factory(event_types=["order.created"])
    payload = {
        "event_type": "order.created",
        "payload": {"order_id": "ord_123"},
        "idempotency_key": "evt-key-1",
    }

    first_response = api_client.post("/api/events/", payload, format="json")
    second_response = api_client.post("/api/events/", payload, format="json")

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert first_response.json()["event_id"] == second_response.json()["event_id"]
    assert second_response.json()["deliveries_created"] == 0
    assert Event.objects.count() == 1
    assert Delivery.objects.count() == 1
