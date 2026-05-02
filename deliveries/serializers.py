import secrets
from urllib.parse import urlparse

from rest_framework import serializers

from deliveries.models import Delivery, WebhookEndpoint


class EventTypesMixin:
    def validate_event_types(self, value: list[str]) -> list[str]:
        if not isinstance(value, list) or not value:
            raise serializers.ValidationError("Provide at least one event type.")
        if not all(isinstance(item, str) and item.strip() for item in value):
            raise serializers.ValidationError("Every event type must be a non-empty string.")
        return [item.strip() for item in value]


class WebhookEndpointCreateSerializer(EventTypesMixin, serializers.ModelSerializer):
    url = serializers.CharField(max_length=2048)
    secret = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = WebhookEndpoint
        fields = [
            "id",
            "url",
            "description",
            "event_types",
            "secret",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "is_active", "created_at"]

    def create(self, validated_data):
        if not validated_data.get("secret"):
            validated_data["secret"] = secrets.token_urlsafe(32)
        return super().create(validated_data)

    def validate_url(self, value: str) -> str:
        value = value.strip()
        parsed = urlparse(value)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise serializers.ValidationError("Provide a valid http or https URL.")
        return value


class WebhookEndpointListSerializer(serializers.ModelSerializer):
    class Meta:
        model = WebhookEndpoint
        fields = ["id", "url", "description", "event_types", "is_active", "created_at"]


class EventPublishSerializer(serializers.Serializer):
    event_type = serializers.CharField(max_length=255)
    payload = serializers.JSONField()
    idempotency_key = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
        allow_null=True,
    )

    def validate_event_type(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("event_type cannot be blank.")
        return value

    def validate_idempotency_key(self, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class DeliveryListSerializer(serializers.ModelSerializer):
    event_type = serializers.CharField(source="event.event_type", read_only=True)
    endpoint_url = serializers.CharField(source="endpoint.url", read_only=True)

    class Meta:
        model = Delivery
        fields = [
            "id",
            "event",
            "event_type",
            "endpoint",
            "endpoint_url",
            "status",
            "attempt_count",
            "next_attempt_at",
            "last_status_code",
            "last_error",
            "created_at",
            "updated_at",
        ]


class DeliveryDetailSerializer(serializers.ModelSerializer):
    event_id = serializers.UUIDField(source="event.id", read_only=True)
    event_type = serializers.CharField(source="event.event_type", read_only=True)
    event_payload = serializers.JSONField(source="event.payload", read_only=True)
    event_created_at = serializers.DateTimeField(source="event.created_at", read_only=True)
    endpoint_info = serializers.SerializerMethodField()

    class Meta:
        model = Delivery
        fields = [
            "id",
            "status",
            "event_id",
            "event_type",
            "event_payload",
            "event_created_at",
            "endpoint",
            "endpoint_info",
            "attempt_count",
            "max_attempts",
            "next_attempt_at",
            "last_attempt_at",
            "last_status_code",
            "last_error",
            "response_body_snippet",
            "replay_count",
            "created_at",
            "updated_at",
        ]

    def get_endpoint_info(self, obj: Delivery) -> dict:
        return {
            "id": str(obj.endpoint_id),
            "url": obj.endpoint.url,
            "description": obj.endpoint.description,
            "event_types": obj.endpoint.event_types,
            "is_active": obj.endpoint.is_active,
        }
