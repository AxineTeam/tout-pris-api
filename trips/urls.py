from django.urls import path

from trips.views import (
    TripDetailView,
    TripItemDetailView,
    TripItemListCreateView,
    TripKitView,
    TripListCreateView,
    TripParticipantDestroyView,
    TripParticipantListCreateView,
)

urlpatterns = [
    path(
        "households/<int:household_id>/trips/",
        TripListCreateView.as_view(),
        name="trips",
    ),
    path(
        "households/<int:household_id>/trips/<int:pk>/",
        TripDetailView.as_view(),
        name="trip",
    ),
    path(
        "households/<int:household_id>/trips/<int:trip_id>/participants/",
        TripParticipantListCreateView.as_view(),
        name="trip-participants",
    ),
    path(
        "households/<int:household_id>/trips/<int:trip_id>/participants/<int:pk>/",
        TripParticipantDestroyView.as_view(),
        name="trip-participant",
    ),
    path(
        "households/<int:household_id>/trips/<int:trip_id>/items/",
        TripItemListCreateView.as_view(),
        name="trip-items",
    ),
    path(
        "households/<int:household_id>/trips/<int:trip_id>/items/<int:pk>/",
        TripItemDetailView.as_view(),
        name="trip-item",
    ),
    path(
        "households/<int:household_id>/trips/<int:trip_id>/kits/",
        TripKitView.as_view(),
        name="trip-kits",
    ),
]
