from django.db import IntegrityError, transaction
from django.db.models import Count, Max
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.utils.http import parse_etags, quote_etag
from django.utils.translation import gettext_lazy as _
from drf_spectacular.utils import (
    OpenApiParameter,
    OpenApiResponse,
    extend_schema,
    extend_schema_view,
)
from rest_framework import generics, serializers
from rest_framework.fields import empty
from rest_framework.response import Response

from households.views import FORBIDDEN, HouseholdScopedView
from tout_pris.exceptions import Conflict
from trips.preparation import NO_STATUS, duplicate_trip, instantiate_kit, starting_status
from trips.serializers import (
    KitInstantiationSerializer,
    TripCreateSerializer,
    TripDetailSerializer,
    TripDuplicationSerializer,
    TripItemCreateSerializer,
    TripItemSerializer,
    TripItemUpdateSerializer,
    TripParticipantCreateSerializer,
    TripParticipantSerializer,
    TripSerializer,
    TripUpdateSerializer,
)

ALREADY_PACKED = _("That object is already in this trip for that person.")

ALREADY_GOING = _("That person already goes on this trip.")

NO_STATUS_RESPONSE = OpenApiResponse(description=NO_STATUS)

ARCHIVED = OpenApiParameter(
    name="archived",
    type=bool,
    default=False,
    description="List the archived trips, most recently archived first, instead of the others.",
)

IF_NONE_MATCH = OpenApiParameter(
    name="If-None-Match",
    type=str,
    location=OpenApiParameter.HEADER,
    description=(
        "Fingerprint the client already holds, sent back to be told whether the lines moved."
    ),
)

UNCHANGED = OpenApiResponse(
    description="No line was added, removed or touched since that fingerprint, and no body is sent."
)


def archived_wanted(request):
    return serializers.BooleanField(default=False).run_validation(
        request.query_params.get("archived", empty)
    )


def trip_detail_queryset(household):
    return household.trips.prefetch_related(
        "participants__person",
        "items__item_type__kit_items__kit",
        "items__person",
        "items__status",
    )


INSTANTIATED = {
    200: OpenApiResponse(
        response=TripItemSerializer(many=True),
        description=(
            "The kit added nothing, every line of it being already in the trip or aimed "
            "at someone who does not go. The array is then empty."
        ),
    ),
    201: TripItemSerializer(many=True),
    403: FORBIDDEN,
    409: NO_STATUS_RESPONSE,
}


@extend_schema_view(
    get=extend_schema(parameters=[ARCHIVED]),
    post=extend_schema(
        request=TripCreateSerializer, responses={201: TripSerializer, 403: FORBIDDEN}
    ),
)
class TripListCreateView(HouseholdScopedView, generics.ListCreateAPIView):
    def get_serializer_class(self):
        return TripCreateSerializer if self.request.method == "POST" else TripSerializer

    def get_queryset(self):
        if archived_wanted(self.request):
            return self.household.trips.filter(archived_at__isnull=False).order_by("-archived_at")
        return self.household.trips.filter(archived_at__isnull=True)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        trip = serializer.save(household=self.household)
        return Response(TripSerializer(trip).data, status=201)


@extend_schema_view(delete=extend_schema(responses={204: None, 403: FORBIDDEN}))
class TripDetailView(HouseholdScopedView, generics.RetrieveDestroyAPIView):
    def get_serializer_class(self):
        return TripUpdateSerializer if self.request.method == "PATCH" else TripDetailSerializer

    def get_queryset(self):
        return trip_detail_queryset(self.household)

    @extend_schema(
        request=TripUpdateSerializer, responses={200: TripDetailSerializer, 403: FORBIDDEN}
    )
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(TripDetailSerializer(serializer.save()).data)


class TripScopedView(HouseholdScopedView):
    @cached_property
    def trip(self):
        return get_object_or_404(self.household.trips, pk=self.kwargs["trip_id"])

    def get_queryset(self):
        return self.trip.items.select_related("item_type", "person", "status").prefetch_related(
            "item_type__kit_items__kit"
        )


@extend_schema_view(
    post=extend_schema(
        request=TripDuplicationSerializer,
        responses={201: TripDetailSerializer, 403: FORBIDDEN, 409: NO_STATUS_RESPONSE},
    )
)
class TripDuplicationView(TripScopedView, generics.CreateAPIView):
    serializer_class = TripDuplicationSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        copy = duplicate_trip(self.trip, **serializer.validated_data)
        return Response(
            TripDetailSerializer(trip_detail_queryset(self.household).get(pk=copy.pk)).data,
            status=201,
        )


class TripParticipantView(TripScopedView):
    def get_queryset(self):
        return self.trip.participants.select_related("person").order_by("id")


@extend_schema_view(
    post=extend_schema(
        request=TripParticipantCreateSerializer,
        responses={
            201: TripParticipantSerializer,
            403: FORBIDDEN,
            409: OpenApiResponse(description=ALREADY_GOING),
        },
    )
)
class TripParticipantListCreateView(TripParticipantView, generics.ListCreateAPIView):
    def get_serializer_class(self):
        return (
            TripParticipantCreateSerializer
            if self.request.method == "POST"
            else TripParticipantSerializer
        )

    def create(self, request, *args, **kwargs):
        trip = self.trip
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                participant = serializer.save(trip=trip)
        except IntegrityError:
            raise Conflict(ALREADY_GOING) from None
        return Response(TripParticipantSerializer(participant).data, status=201)


@extend_schema_view(delete=extend_schema(responses={204: None, 403: FORBIDDEN}))
class TripParticipantDestroyView(TripParticipantView, generics.DestroyAPIView):
    serializer_class = TripParticipantSerializer


@extend_schema_view(
    get=extend_schema(
        parameters=[IF_NONE_MATCH],
        responses={200: TripItemSerializer(many=True), 304: UNCHANGED},
    ),
    post=extend_schema(
        request=TripItemCreateSerializer,
        responses={
            201: TripItemSerializer,
            403: FORBIDDEN,
            409: OpenApiResponse(description=f"{ALREADY_PACKED} {NO_STATUS}"),
        },
    ),
)
class TripItemListCreateView(TripScopedView, generics.ListCreateAPIView):
    def get_serializer_class(self):
        return TripItemCreateSerializer if self.request.method == "POST" else TripItemSerializer

    def list(self, request, *args, **kwargs):
        stamp = self.get_queryset().aggregate(last=Max("updated_at"), lines=Count("pk"))
        etag = quote_etag(f"{stamp['last'].timestamp() if stamp['last'] else 0}:{stamp['lines']}")
        held = parse_etags(request.headers.get("If-None-Match", ""))
        unchanged = etag in held or "*" in held
        response = Response(status=304) if unchanged else super().list(request, *args, **kwargs)
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "no-cache"
        return response

    def create(self, request, *args, **kwargs):
        trip = self.trip
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status = serializer.validated_data.get("status") or starting_status(trip.household_id)
        try:
            with transaction.atomic():
                line = serializer.save(trip=trip, status=status)
        except IntegrityError:
            raise Conflict(ALREADY_PACKED) from None
        return Response(TripItemSerializer(self.get_queryset().get(pk=line.pk)).data, status=201)


@extend_schema_view(delete=extend_schema(responses={204: None, 403: FORBIDDEN}))
class TripItemDetailView(TripScopedView, generics.RetrieveDestroyAPIView):
    def get_serializer_class(self):
        return TripItemUpdateSerializer if self.request.method == "PATCH" else TripItemSerializer

    @extend_schema(
        request=TripItemUpdateSerializer,
        responses={
            200: TripItemSerializer,
            403: FORBIDDEN,
            409: OpenApiResponse(description=ALREADY_PACKED),
        },
    )
    def patch(self, request, *args, **kwargs):
        line = self.get_object()
        serializer = self.get_serializer(line, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                serializer.save()
        except IntegrityError:
            raise Conflict(ALREADY_PACKED) from None
        return Response(TripItemSerializer(self.get_queryset().get(pk=line.pk)).data)


@extend_schema_view(post=extend_schema(request=KitInstantiationSerializer, responses=INSTANTIATED))
class TripKitView(TripScopedView, generics.CreateAPIView):
    serializer_class = KitInstantiationSerializer

    def create(self, request, *args, **kwargs):
        trip = self.trip
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            created = instantiate_kit(trip, serializer.validated_data["kit"])
        except IntegrityError:
            created = instantiate_kit(trip, serializer.validated_data["kit"])
        lines = self.get_queryset().filter(pk__in=[line.pk for line in created])
        return Response(TripItemSerializer(lines, many=True).data, status=201 if created else 200)
