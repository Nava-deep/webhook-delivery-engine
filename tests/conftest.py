import pytest
from rest_framework.test import APIClient

from deliveries.models import Delivery, Event, WebhookEndpoint


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def endpoint_factory(db):
    def create_endpoint(**overrides):
        defaults = {
            "url": "http://example.com/webhook",
            "description": "Example receiver",
            "event_types": ["order.created"],
            "secret": "test-secret",
            "is_active": True,
        }
        defaults.update(overrides)
        return WebhookEndpoint.objects.create(**defaults)

    return create_endpoint


@pytest.fixture
def event_factory(db):
    def create_event(**overrides):
        defaults = {
            "event_type": "order.created",
            "payload": {"order_id": "ord_123", "amount": 1999},
        }
        defaults.update(overrides)
        return Event.objects.create(**defaults)

    return create_event


@pytest.fixture
def delivery_factory(db, endpoint_factory, event_factory):
    def create_delivery(**overrides):
        endpoint = overrides.pop("endpoint", endpoint_factory())
        event = overrides.pop("event", event_factory())
        defaults = {
            "event": event,
            "endpoint": endpoint,
            "status": Delivery.Status.PENDING,
        }
        defaults.update(overrides)
        return Delivery.objects.create(**defaults)

    return create_delivery
