from django.urls import path

from households.views import (
    HouseholdListView,
    InvitationAcceptView,
    InvitationDestroyView,
    InvitationListCreateView,
)

urlpatterns = [
    path("households/", HouseholdListView.as_view(), name="households"),
    path(
        "households/<int:household_id>/invitations/",
        InvitationListCreateView.as_view(),
        name="invitations",
    ),
    path(
        "households/<int:household_id>/invitations/<int:pk>/",
        InvitationDestroyView.as_view(),
        name="invitation",
    ),
    path("invitations/accept/", InvitationAcceptView.as_view(), name="accept-invitation"),
]
