from django.urls import include, path
from rest_framework.routers import DefaultRouter

from deliveries.views import (
    DeliveryViewSet,
    EventViewSet,
    StatsAPIView,
    WebhookEndpointViewSet,
)


router = DefaultRouter()
router.register("endpoints", WebhookEndpointViewSet, basename="endpoint")
router.register("events", EventViewSet, basename="event")
router.register("deliveries", DeliveryViewSet, basename="delivery")

urlpatterns = [
    path("", include(router.urls)),
    path("stats/", StatsAPIView.as_view(), name="stats"),
]
