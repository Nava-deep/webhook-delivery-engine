import pytest

from deliveries.models import Delivery


pytestmark = pytest.mark.django_db


def test_delivery_filters_work(api_client, endpoint_factory, event_factory):
    endpoint_a = endpoint_factory(url="http://a.test/webhook")
    endpoint_b = endpoint_factory(url="http://b.test/webhook")
    order_event = event_factory(event_type="order.created")
    payment_event = event_factory(event_type="payment.succeeded")
    failed_delivery = Delivery.objects.create(
        event=order_event,
        endpoint=endpoint_a,
        status=Delivery.Status.FAILED,
    )
    Delivery.objects.create(
        event=payment_event,
        endpoint=endpoint_b,
        status=Delivery.Status.DELIVERED,
    )

    by_status = api_client.get("/api/deliveries/?status=failed")
    by_event_type = api_client.get("/api/deliveries/?event_type=order.created")
    by_endpoint = api_client.get(f"/api/deliveries/?endpoint_id={endpoint_a.id}")

    assert by_status.status_code == 200
    assert by_event_type.status_code == 200
    assert by_endpoint.status_code == 200
    assert [item["id"] for item in by_status.json()] == [str(failed_delivery.id)]
    assert [item["id"] for item in by_event_type.json()] == [str(failed_delivery.id)]
    assert [item["id"] for item in by_endpoint.json()] == [str(failed_delivery.id)]


def test_stats_endpoint_returns_correct_counts(api_client, endpoint_factory, event_factory):
    endpoint = endpoint_factory()
    order_event = event_factory(event_type="order.created")
    payment_event = event_factory(event_type="payment.succeeded")
    Delivery.objects.create(
        event=order_event,
        endpoint=endpoint,
        status=Delivery.Status.PENDING,
        attempt_count=0,
    )
    Delivery.objects.create(
        event=payment_event,
        endpoint=endpoint,
        status=Delivery.Status.DELIVERED,
        attempt_count=2,
    )
    Delivery.objects.create(
        event=payment_event,
        endpoint=endpoint,
        status=Delivery.Status.FAILED,
        attempt_count=1,
    )
    Delivery.objects.create(
        event=payment_event,
        endpoint=endpoint,
        status=Delivery.Status.DEAD_LETTERED,
        attempt_count=5,
    )

    response = api_client.get("/api/stats/")

    assert response.status_code == 200
    assert response.json() == {
        "total_events": 2,
        "total_deliveries": 4,
        "pending": 1,
        "delivered": 1,
        "failed": 1,
        "dead_lettered": 1,
        "average_attempts": 2.0,
        "success_rate": 25.0,
    }
