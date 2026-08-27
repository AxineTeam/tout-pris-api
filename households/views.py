from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.functional import cached_property
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from households.invitations import accept, invite, pending_invitation
from households.memberships import create_household, remove_member
from households.models import Household, HouseholdRole, Invitation
from households.permissions import (
    IsHouseholdOwner,
    IsHouseholdOwnerOrLeavingThemselves,
    IsSomeoneInTheHousehold,
)
from households.serializers import (
    HouseholdCreateSerializer,
    HouseholdSerializer,
    HouseholdUpdateSerializer,
    InvitationAcceptSerializer,
    InvitationCreateSerializer,
    InvitationSerializer,
    MemberSerializer,
    MemberUpdateSerializer,
    PersonCreateSerializer,
    PersonSerializer,
    PersonUpdateSerializer,
)
from tout_pris.exceptions import Conflict

FORBIDDEN = OpenApiResponse(
    description="The caller is a member of this household, but their role does not allow that."
)


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
    permission_classes = [IsAuthenticated, IsSomeoneInTheHousehold]

    def household_queryset(self):
        return Household.objects.filter(members__user=self.request.user)

    @cached_property
    def household(self):
        return get_object_or_404(self.household_queryset(), pk=self.kwargs["household_id"])

    def get_serializer_context(self):
        return {**super().get_serializer_context(), "household": self.household}


class SharedHouseholdScopedView(HouseholdScopedView):
    def household_queryset(self):
        return super().household_queryset().filter(personal_of__isnull=True)


class HouseholdDetailView(SharedHouseholdScopedView):
    permission_classes = [IsAuthenticated, IsHouseholdOwner, IsSomeoneInTheHousehold]
    serializer_class = HouseholdUpdateSerializer

    @extend_schema(
        request=HouseholdUpdateSerializer, responses={200: HouseholdSerializer, 403: FORBIDDEN}
    )
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.household, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(HouseholdSerializer(serializer.save()).data)

    @extend_schema(responses={204: None, 403: FORBIDDEN})
    def delete(self, request, *args, **kwargs):
        self.household.delete()
        return Response(status=204)


@extend_schema_view(
    post=extend_schema(request=PersonCreateSerializer, responses={201: PersonSerializer})
)
class PersonListCreateView(HouseholdScopedView, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]

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
            403: FORBIDDEN,
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

    @extend_schema(
        request=PersonUpdateSerializer, responses={200: PersonSerializer, 403: FORBIDDEN}
    )
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(PersonSerializer(serializer.save()).data)

    def perform_destroy(self, person):
        if person.user_id and self.household.members.filter(user=person.user_id).exists():
            raise Conflict("A person whose account is still a member cannot be deleted.")
        person.delete()


@extend_schema_view(
    post=extend_schema(
        request=None,
        responses={
            204: None,
            409: OpenApiResponse(
                description=(
                    "That person already has an account, "
                    "or the caller already is someone in this household."
                )
            ),
        },
    )
)
class PersonClaimView(HouseholdScopedView):
    permission_classes = [IsAuthenticated]
    serializer_class = PersonSerializer

    def post(self, request, *args, **kwargs):
        person = get_object_or_404(self.household.persons, pk=self.kwargs["pk"])
        if self.household.persons.filter(user=request.user).exists():
            raise Conflict("The caller already is someone in this household.")
        claimed = self.household.persons.filter(pk=person.pk, user__isnull=True).update(
            user=request.user
        )
        if not claimed:
            raise Conflict("That person already has an account.")
        return Response(status=204)


class MemberListView(SharedHouseholdScopedView, generics.ListAPIView):
    serializer_class = MemberSerializer

    def get_queryset(self):
        return self.household.members.select_related("user").order_by("id")


@extend_schema_view(
    patch=extend_schema(
        request=MemberUpdateSerializer,
        responses={
            200: MemberSerializer,
            403: FORBIDDEN,
            409: OpenApiResponse(
                description=(
                    "The last owner cannot step down, and a member who is nobody in the "
                    "household yet cannot be made an owner."
                )
            ),
        },
    ),
    delete=extend_schema(
        responses={
            204: None,
            403: FORBIDDEN,
            409: OpenApiResponse(
                description=(
                    "The last member cannot leave, and the last owner cannot leave either."
                )
            ),
        },
    ),
)
class MemberDetailView(SharedHouseholdScopedView, generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsHouseholdOwnerOrLeavingThemselves]

    def get_serializer_class(self):
        return MemberUpdateSerializer if self.request.method == "PATCH" else MemberSerializer

    def get_queryset(self):
        return self.household.members.all()

    def patch(self, request, *args, **kwargs):
        member = self.get_object()
        serializer = self.get_serializer(member, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        role = serializer.validated_data.get("role")
        if role == HouseholdRole.MEMBER and self.is_last_owner(member):
            raise Conflict("The last owner cannot step down, hand the role over first.")
        if (
            role == HouseholdRole.OWNER
            and not self.household.persons.filter(user=member.user_id).exists()
        ):
            raise Conflict("A member who is nobody in this household yet cannot be made an owner.")
        return Response(MemberSerializer(serializer.save()).data)

    def perform_destroy(self, member):
        if self.household.members.count() == 1:
            raise Conflict("The last member cannot leave, delete the household instead.")
        if self.is_last_owner(member):
            raise Conflict("The last owner cannot leave, hand the role over first.")
        remove_member(member)

    def is_last_owner(self, member):
        owners = self.household.members.filter(role=HouseholdRole.OWNER)
        return member.role == HouseholdRole.OWNER and owners.count() == 1


@extend_schema_view(
    post=extend_schema(request=InvitationCreateSerializer, responses={204: None, 403: FORBIDDEN})
)
class InvitationListCreateView(SharedHouseholdScopedView, generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated, IsHouseholdOwner, IsSomeoneInTheHousehold]
    throttle_scope = "invitations"

    def get_throttles(self):
        return [ScopedRateThrottle()] if self.request.method == "POST" else []

    def get_serializer_class(self):
        return InvitationCreateSerializer if self.request.method == "POST" else InvitationSerializer

    def get_queryset(self):
        return Invitation.objects.filter(
            household=self.household, accepted_at=None, expires_at__gt=timezone.now()
        ).order_by("created_at")

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite(self.household, serializer.validated_data["email"], request.user)
        return Response(status=204)


@extend_schema_view(delete=extend_schema(responses={204: None, 403: FORBIDDEN}))
class InvitationDestroyView(SharedHouseholdScopedView, generics.DestroyAPIView):
    permission_classes = [IsAuthenticated, IsHouseholdOwner, IsSomeoneInTheHousehold]
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
