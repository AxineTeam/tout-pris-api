from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.functional import cached_property
from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from households.invitations import accept, invite, pending_invitation
from households.models import Household, Invitation
from households.serializers import (
    HouseholdSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
)


class HouseholdListView(generics.ListAPIView):
    serializer_class = HouseholdSerializer

    def get_queryset(self):
        return (
            Household.objects.filter(members__user=self.request.user)
            .alias(personal=Q(personal_of__isnull=False))
            .order_by("-personal", "created_at")
        )


class HouseholdScopedView(generics.GenericAPIView):
    def household_queryset(self):
        return Household.objects.filter(members__user=self.request.user)

    @cached_property
    def household(self):
        return get_object_or_404(self.household_queryset(), pk=self.kwargs["household_id"])


class SharedHouseholdScopedView(HouseholdScopedView):
    def household_queryset(self):
        return super().household_queryset().filter(personal_of__isnull=True)


class InvitationListCreateView(SharedHouseholdScopedView, generics.ListCreateAPIView):
    throttle_scope = "invitations"

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def get_serializer_class(self):
        return InvitationCreateSerializer if self.request.method == "POST" else InvitationSerializer

    def get_serializer_context(self):
        return super().get_serializer_context() | {"household": self.household}

    def get_queryset(self):
        return Invitation.objects.filter(
            household=self.household, accepted_at=None, expires_at__gt=timezone.now()
        ).order_by("created_at")

    @extend_schema(request=InvitationCreateSerializer, responses={204: None})
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite(
            self.household,
            serializer.validated_data["email"],
            request.user,
            serializer.validated_data.get("person"),
        )
        return Response(status=204)


class InvitationDestroyView(SharedHouseholdScopedView, generics.DestroyAPIView):
    serializer_class = InvitationSerializer

    def get_queryset(self):
        return Invitation.objects.filter(household=self.household, accepted_at=None)


class InvitationAcceptView(APIView):
    @extend_schema(request=InvitationAcceptSerializer, responses={200: HouseholdSerializer})
    def post(self, request):
        serializer = InvitationAcceptSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = pending_invitation(serializer.validated_data["token"])
        if invitation is None:
            raise Http404
        household = accept(invitation, request.user)
        return Response(HouseholdSerializer(household).data)
