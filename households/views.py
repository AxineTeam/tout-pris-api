from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.functional import cached_property
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from households.invitations import accept, invite, pending_invitation
from households.memberships import create_household, remove_member
from households.models import Household, Invitation
from households.serializers import (
    HouseholdCreateSerializer,
    HouseholdSerializer,
    HouseholdUpdateSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    MemberSerializer,
    PersonCreateSerializer,
    PersonSerializer,
    PersonUpdateSerializer,
)


class Conflict(APIException):
    status_code = 409


@extend_schema_view(
    post=extend_schema(request=HouseholdCreateSerializer, responses={201: HouseholdSerializer})
)
class HouseholdListCreateView(generics.ListCreateAPIView):
    def get_serializer_class(self):
        return HouseholdCreateSerializer if self.request.method == "POST" else HouseholdSerializer

    def get_queryset(self):
        return (
            Household.objects.filter(members__user=self.request.user)
            .alias(personal=Q(personal_of__isnull=False))
            .order_by("-personal", "created_at")
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        household = create_household(serializer.validated_data["name"], request.user)
        return Response(HouseholdSerializer(household).data, status=201)


class HouseholdScopedView(generics.GenericAPIView):
    def household_queryset(self):
        return Household.objects.filter(members__user=self.request.user)

    @cached_property
    def household(self):
        return get_object_or_404(self.household_queryset(), pk=self.kwargs["household_id"])


class SharedHouseholdScopedView(HouseholdScopedView):
    def household_queryset(self):
        return super().household_queryset().filter(personal_of__isnull=True)


class HouseholdDetailView(SharedHouseholdScopedView):
    serializer_class = HouseholdUpdateSerializer

    @extend_schema(request=HouseholdUpdateSerializer, responses={200: HouseholdSerializer})
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.household, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(HouseholdSerializer(serializer.save()).data)

    @extend_schema(responses={204: None})
    def delete(self, request, *args, **kwargs):
        self.household.delete()
        return Response(status=204)


@extend_schema_view(
    post=extend_schema(request=PersonCreateSerializer, responses={201: PersonSerializer})
)
class PersonListCreateView(HouseholdScopedView, generics.ListCreateAPIView):
    def get_serializer_class(self):
        return PersonCreateSerializer if self.request.method == "POST" else PersonSerializer

    def get_queryset(self):
        return self.household.persons.order_by("id")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        person = serializer.save(household=self.household)
        return Response(PersonSerializer(person).data, status=201)


@extend_schema_view(
    delete=extend_schema(
        responses={
            204: None,
            409: OpenApiResponse(
                description="The account of that person is still a member of the household."
            ),
        }
    )
)
class PersonDetailView(HouseholdScopedView, generics.RetrieveDestroyAPIView):
    def get_serializer_class(self):
        return PersonUpdateSerializer if self.request.method == "PATCH" else PersonSerializer

    def get_queryset(self):
        return self.household.persons.all()

    @extend_schema(request=PersonUpdateSerializer, responses={200: PersonSerializer})
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(PersonSerializer(serializer.save()).data)

    def perform_destroy(self, person):
        if person.user_id and self.household.members.filter(user=person.user_id).exists():
            raise Conflict("A person whose account is still a member cannot be deleted.")
        person.delete()


class MemberListView(SharedHouseholdScopedView, generics.ListAPIView):
    serializer_class = MemberSerializer

    def get_queryset(self):
        return self.household.members.select_related("user").order_by("id")


@extend_schema_view(
    delete=extend_schema(
        responses={
            204: None,
            409: OpenApiResponse(
                description="The last member cannot leave, the household is deleted instead."
            ),
        }
    )
)
class MemberDestroyView(SharedHouseholdScopedView, generics.DestroyAPIView):
    serializer_class = MemberSerializer

    def get_queryset(self):
        return self.household.members.all()

    def perform_destroy(self, member):
        if self.household.members.count() == 1:
            raise Conflict("The last member cannot leave, delete the household instead.")
        remove_member(member)


@extend_schema_view(post=extend_schema(request=InvitationCreateSerializer, responses={204: None}))
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
