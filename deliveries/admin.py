from django.contrib import admin

from deliveries.models import Delivery, Event, WebhookEndpoint


@admin.register(WebhookEndpoint)
class WebhookEndpointAdmin(admin.ModelAdmin):
    list_display = ("id", "url", "is_active", "created_at")
    search_fields = ("url", "description")
    list_filter = ("is_active",)


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("id", "event_type", "idempotency_key", "created_at")
    search_fields = ("event_type", "idempotency_key")


@admin.register(Delivery)
class DeliveryAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "event",
        "endpoint",
        "status",
        "attempt_count",
        "next_attempt_at",
        "updated_at",
    )
    list_filter = ("status",)
    search_fields = ("id", "event__event_type", "endpoint__url")
