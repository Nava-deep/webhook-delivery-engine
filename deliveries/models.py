import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def validate_event_types(value: list[str]) -> None:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValidationError("event_types must be a list of strings.")


class WebhookEndpoint(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    url = models.URLField(max_length=2048)
    description = models.TextField(blank=True)
    event_types = models.JSONField(default=list, validators=[validate_event_types])
    secret = models.CharField(max_length=255)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.url


class Event(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_type = models.CharField(max_length=255, db_index=True)
    payload = models.JSONField()
    idempotency_key = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["event_type", "created_at"])]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event_type} ({self.id})"


class Delivery(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DELIVERING = "delivering", "Delivering"
        DELIVERED = "delivered", "Delivered"
        FAILED = "failed", "Failed"
        DEAD_LETTERED = "dead_lettered", "Dead-lettered"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event = models.ForeignKey(Event, related_name="deliveries", on_delete=models.CASCADE)
    endpoint = models.ForeignKey(
        WebhookEndpoint,
        related_name="deliveries",
        on_delete=models.CASCADE,
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    attempt_count = models.PositiveIntegerField(default=0)
    max_attempts = models.PositiveIntegerField(default=5)
    next_attempt_at = models.DateTimeField(default=timezone.now, null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)
    last_status_code = models.PositiveIntegerField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    response_body_snippet = models.TextField(blank=True)
    replay_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["status", "next_attempt_at"]),
            models.Index(fields=["created_at"]),
        ]
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.event.event_type} -> {self.endpoint.url} ({self.status})"
