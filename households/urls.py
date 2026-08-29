from django.urls import path

from households.views import (
    HouseholdDetailView,
    HouseholdListCreateView,
    InvitationAcceptView,
    InvitationDestroyView,
    InvitationListCreateView,
    InvitationPreviewView,
    MemberDetailView,
    MemberListView,
    PersonClaimView,
    PersonDetailView,
    PersonListCreateView,
)

urlpatterns = [
    path("households/", HouseholdListCreateView.as_view(), name="households"),
    path("households/<int:household_id>/", HouseholdDetailView.as_view(), name="household"),
    path("households/<int:household_id>/persons/", PersonListCreateView.as_view(), name="persons"),
    path(
        "households/<int:household_id>/persons/<int:pk>/",
        PersonDetailView.as_view(),
        name="person",
    ),
    path(
        "households/<int:household_id>/persons/<int:pk>/claim/",
        PersonClaimView.as_view(),
        name="claim-person",
    ),
    path("households/<int:household_id>/members/", MemberListView.as_view(), name="members"),
    path(
        "households/<int:household_id>/members/<int:pk>/",
        MemberDetailView.as_view(),
        name="member",
    ),
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
    path("invitations/<str:token>/", InvitationPreviewView.as_view(), name="preview-invitation"),
]
