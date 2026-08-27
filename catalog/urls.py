from django.urls import path

from catalog.views import (
    ItemStatusDetailView,
    ItemStatusListCreateView,
    ItemTypeDetailView,
    ItemTypeListCreateView,
    KitDetailView,
    KitItemDetailView,
    KitItemListCreateView,
    KitListCreateView,
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
    path(
        "households/<int:household_id>/kits/",
        KitListCreateView.as_view(),
        name="kits",
    ),
    path(
        "households/<int:household_id>/kits/<int:pk>/",
        KitDetailView.as_view(),
        name="kit",
    ),
    path(
        "households/<int:household_id>/kits/<int:kit_id>/items/",
        KitItemListCreateView.as_view(),
        name="kit-items",
    ),
    path(
        "households/<int:household_id>/kits/<int:kit_id>/items/<int:pk>/",
        KitItemDetailView.as_view(),
        name="kit-item",
    ),
]
