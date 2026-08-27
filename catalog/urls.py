from django.urls import path

from catalog.views import (
    ItemStatusDetailView,
    ItemStatusListCreateView,
    ItemTypeDetailView,
    ItemTypeListCreateView,
)

urlpatterns = [
    path(
        "households/<int:household_id>/item-types/",
        ItemTypeListCreateView.as_view(),
        name="item-types",
    ),
    path(
        "households/<int:household_id>/item-types/<int:pk>/",
        ItemTypeDetailView.as_view(),
        name="item-type",
    ),
    path(
        "households/<int:household_id>/item-statuses/",
        ItemStatusListCreateView.as_view(),
        name="item-statuses",
    ),
    path(
        "households/<int:household_id>/item-statuses/<int:pk>/",
        ItemStatusDetailView.as_view(),
        name="item-status",
    ),
]
