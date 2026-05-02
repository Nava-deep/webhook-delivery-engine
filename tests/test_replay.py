import pytest

from deliveries.models import Delivery


pytestmark = pytest.mark.django_db


def test_manual_replay_resets_failed_delivery_to_pending(api_client, delivery_factory):
    delivery = delivery_factory(
        status=Delivery.Status.FAILED,
        attempt_count=3,
        last_error="Previous failure",
    )

    response = api_client.post(f"/api/deliveries/{delivery.id}/replay/")

    assert response.status_code == 200
    delivery.refresh_from_db()
    assert delivery.status == Delivery.Status.PENDING
    assert delivery.attempt_count == 0
    assert delivery.replay_count == 1
    assert delivery.next_attempt_at is not None
    assert response.json()["status"] == Delivery.Status.PENDING


def test_manual_replay_resets_dead_lettered_delivery_to_pending(
    api_client,
    delivery_factory,
):
    delivery = delivery_factory(
        status=Delivery.Status.DEAD_LETTERED,
        attempt_count=5,
        max_attempts=5,
    )

    response = api_client.post(f"/api/deliveries/{delivery.id}/replay/")

    assert response.status_code == 200
    delivery.refresh_from_db()
    assert delivery.status == Delivery.Status.PENDING
    assert delivery.attempt_count == 0
    assert delivery.replay_count == 1


def test_manual_replay_rejects_delivered_delivery(api_client, delivery_factory):
    delivery = delivery_factory(status=Delivery.Status.DELIVERED)

    response = api_client.post(f"/api/deliveries/{delivery.id}/replay/")

    assert response.status_code == 400
    assert "Only failed or dead-lettered" in response.json()["detail"]
