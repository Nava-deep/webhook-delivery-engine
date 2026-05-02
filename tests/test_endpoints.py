import pytest

from deliveries.models import WebhookEndpoint


pytestmark = pytest.mark.django_db


def test_endpoint_registration_works(api_client):
    response = api_client.post(
        "/api/endpoints/",
        {
            "url": "http://mock-receiver:9000/webhook",
            "description": "Test receiver",
            "event_types": ["order.created", "payment.succeeded"],
        },
        format="json",
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["secret"]
    assert body["url"] == "http://mock-receiver:9000/webhook"

    endpoint = WebhookEndpoint.objects.get(id=body["id"])
    assert endpoint.secret == body["secret"]
    assert endpoint.event_types == ["order.created", "payment.succeeded"]
    assert endpoint.is_active is True


def test_endpoint_registration_accepts_provided_secret(api_client):
    response = api_client.post(
        "/api/endpoints/",
        {
            "url": "http://example.com/webhook",
            "description": "Receiver with known secret",
            "event_types": ["invoice.failed"],
            "secret": "provided-secret",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.json()["secret"] == "provided-secret"


def test_endpoint_list_does_not_expose_secret(api_client, endpoint_factory):
    endpoint_factory(secret="do-not-return-me")

    response = api_client.get("/api/endpoints/")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert "secret" not in body[0]
    assert body[0]["url"] == "http://example.com/webhook"
