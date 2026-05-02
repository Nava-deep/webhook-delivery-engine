import time

from django.core.management.base import BaseCommand
from django.db import OperationalError, ProgrammingError
from django.db.models import F
from django.utils import timezone

from deliveries.models import Delivery
from deliveries.services.delivery import deliver_once


class Command(BaseCommand):
    help = "Continuously process pending webhook deliveries."

    def add_arguments(self, parser):
        parser.add_argument("--once", action="store_true", help="Run one polling cycle.")
        parser.add_argument("--batch-size", type=int, default=20)
        parser.add_argument("--poll-interval", type=float, default=2.0)
        parser.add_argument(
            "--ignore-schedule",
            action="store_true",
            help="Process retryable deliveries even if next_attempt_at is in the future.",
        )

    def handle(self, *args, **options):
        once = options["once"]
        batch_size = options["batch_size"]
        poll_interval = options["poll_interval"]
        ignore_schedule = options["ignore_schedule"]

        self.stdout.write(self.style.SUCCESS("Delivery worker started"))
        while True:
            try:
                queryset = Delivery.objects.filter(
                    status__in=[Delivery.Status.PENDING, Delivery.Status.FAILED],
                    attempt_count__lt=F("max_attempts"),
                )
                if not ignore_schedule:
                    queryset = queryset.filter(next_attempt_at__lte=timezone.now())

                delivery_ids = list(
                    queryset
                    .order_by("next_attempt_at", "created_at")
                    .values_list("id", flat=True)[:batch_size]
                )
            except (OperationalError, ProgrammingError) as exc:
                if once:
                    raise
                self.stdout.write(f"Database is not ready yet: {exc}")
                time.sleep(poll_interval)
                continue

            for delivery_id in delivery_ids:
                delivery = deliver_once(delivery_id)
                self.stdout.write(
                    f"{delivery.id} -> {delivery.status} "
                    f"(attempts={delivery.attempt_count})"
                )

            if once:
                break
            time.sleep(poll_interval)
