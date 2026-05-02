import django.db.models.deletion
import django.utils.timezone
import uuid
from django.db import migrations, models

import deliveries.models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Event",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("event_type", models.CharField(db_index=True, max_length=255)),
                ("payload", models.JSONField()),
                (
                    "idempotency_key",
                    models.CharField(
                        blank=True,
                        db_index=True,
                        max_length=255,
                        null=True,
                        unique=True,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="WebhookEndpoint",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("url", models.URLField(max_length=2048)),
                ("description", models.TextField(blank=True)),
                (
                    "event_types",
                    models.JSONField(
                        default=list,
                        validators=[deliveries.models.validate_event_types],
                    ),
                ),
                ("secret", models.CharField(max_length=255)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Delivery",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("delivering", "Delivering"),
                            ("delivered", "Delivered"),
                            ("failed", "Failed"),
                            ("dead_lettered", "Dead-lettered"),
                        ],
                        db_index=True,
                        default="pending",
                        max_length=32,
                    ),
                ),
                ("attempt_count", models.PositiveIntegerField(default=0)),
                ("max_attempts", models.PositiveIntegerField(default=5)),
                (
                    "next_attempt_at",
                    models.DateTimeField(
                        blank=True,
                        default=django.utils.timezone.now,
                        null=True,
                    ),
                ),
                ("last_attempt_at", models.DateTimeField(blank=True, null=True)),
                ("last_status_code", models.PositiveIntegerField(blank=True, null=True)),
                ("last_error", models.TextField(blank=True)),
                ("response_body_snippet", models.TextField(blank=True)),
                ("replay_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "endpoint",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="deliveries.webhookendpoint",
                    ),
                ),
                (
                    "event",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="deliveries",
                        to="deliveries.event",
                    ),
                ),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="event",
            index=models.Index(
                fields=["event_type", "created_at"],
                name="deliveries__event_t_fa4423_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="webhookendpoint",
            index=models.Index(fields=["is_active"], name="deliveries__is_acti_e723b1_idx"),
        ),
        migrations.AddIndex(
            model_name="webhookendpoint",
            index=models.Index(fields=["created_at"], name="deliveries__created_0c3c74_idx"),
        ),
        migrations.AddIndex(
            model_name="delivery",
            index=models.Index(
                fields=["status", "next_attempt_at"],
                name="deliveries__status_8b9254_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="delivery",
            index=models.Index(fields=["created_at"], name="deliveries__created_e4dbfc_idx"),
        ),
    ]
