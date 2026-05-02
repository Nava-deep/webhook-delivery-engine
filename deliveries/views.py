from django.db import IntegrityError, transaction
from django.db.models import Avg, Count
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from deliveries.models import Delivery, Event, WebhookEndpoint
from deliveries.serializers import (
    DeliveryDetailSerializer,
    DeliveryListSerializer,
    EventPublishSerializer,
    WebhookEndpointCreateSerializer,
    WebhookEndpointListSerializer,
)


class WebhookEndpointViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = WebhookEndpoint.objects.all()

    def get_serializer_class(self):
        if self.action == "create":
            return WebhookEndpointCreateSerializer
        return WebhookEndpointListSerializer


class EventViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    serializer_class = EventPublishSerializer
    queryset = Event.objects.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        idempotency_key = data.get("idempotency_key")

        if idempotency_key:
            existing_event = Event.objects.filter(
                idempotency_key=idempotency_key
            ).first()
            if existing_event:
                return Response(
                    {
                        "event_id": str(existing_event.id),
                        "event_type": existing_event.event_type,
                        "deliveries_created": 0,
                        "idempotent": True,
                    },
                    status=status.HTTP_200_OK,
                )

        try:
            with transaction.atomic():
                event = Event.objects.create(
                    event_type=data["event_type"],
                    payload=data["payload"],
                    idempotency_key=idempotency_key,
                )
                endpoints = [
                    endpoint
                    for endpoint in WebhookEndpoint.objects.filter(is_active=True)
                    if event.event_type in endpoint.event_types
                ]
                deliveries = [
                    Delivery(event=event, endpoint=endpoint) for endpoint in endpoints
                ]
                Delivery.objects.bulk_create(deliveries)
        except IntegrityError:
            existing_event = Event.objects.get(idempotency_key=idempotency_key)
            return Response(
                {
                    "event_id": str(existing_event.id),
                    "event_type": existing_event.event_type,
                    "deliveries_created": 0,
                    "idempotent": True,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {
                "event_id": str(event.id),
                "event_type": event.event_type,
                "deliveries_created": len(deliveries),
                "idempotent": False,
            },
            status=status.HTTP_201_CREATED,
        )


class DeliveryViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Delivery.objects.select_related("event", "endpoint").all()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return DeliveryDetailSerializer
        return DeliveryListSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        status_filter = self.request.query_params.get("status")
        event_type = self.request.query_params.get("event_type")
        endpoint_id = self.request.query_params.get("endpoint_id")

        if status_filter:
            queryset = queryset.filter(status=status_filter)
        if event_type:
            queryset = queryset.filter(event__event_type=event_type)
        if endpoint_id:
            queryset = queryset.filter(endpoint_id=endpoint_id)
        return queryset

    @action(detail=True, methods=["post"])
    def replay(self, request, pk=None):
        delivery = self.get_object()
        if delivery.status not in [
            Delivery.Status.FAILED,
            Delivery.Status.DEAD_LETTERED,
        ]:
            return Response(
                {"detail": "Only failed or dead-lettered deliveries can be replayed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        delivery.status = Delivery.Status.PENDING
        delivery.next_attempt_at = timezone.now()
        delivery.attempt_count = 0
        delivery.replay_count += 1
        delivery.save(
            update_fields=[
                "status",
                "next_attempt_at",
                "attempt_count",
                "replay_count",
                "updated_at",
            ]
        )
        return Response(
            {
                "delivery_id": str(delivery.id),
                "status": delivery.status,
                "replay_count": delivery.replay_count,
                "next_attempt_at": delivery.next_attempt_at,
            }
        )


class StatsAPIView(APIView):
    def get(self, request):
        total_events = Event.objects.count()
        total_deliveries = Delivery.objects.count()
        status_counts = {
            row["status"]: row["count"]
            for row in Delivery.objects.values("status").annotate(count=Count("id"))
        }
        delivered = status_counts.get(Delivery.Status.DELIVERED, 0)
        average_attempts = (
            Delivery.objects.aggregate(value=Avg("attempt_count"))["value"] or 0
        )
        success_rate = (
            round((delivered / total_deliveries) * 100, 2)
            if total_deliveries
            else 0
        )

        return Response(
            {
                "total_events": total_events,
                "total_deliveries": total_deliveries,
                "pending": status_counts.get(Delivery.Status.PENDING, 0),
                "delivered": delivered,
                "failed": status_counts.get(Delivery.Status.FAILED, 0),
                "dead_lettered": status_counts.get(Delivery.Status.DEAD_LETTERED, 0),
                "average_attempts": round(float(average_attempts), 2),
                "success_rate": success_rate,
            }
        )
