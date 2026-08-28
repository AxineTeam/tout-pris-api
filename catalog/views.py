from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import generics
from rest_framework.response import Response

from catalog.item_types import matching_item_type, rename_item_type
from catalog.serializers import (
    ItemStatusCreateSerializer,
    ItemStatusSerializer,
    ItemStatusUpdateSerializer,
    ItemTypeCreateSerializer,
    ItemTypeSerializer,
    ItemTypeUpdateSerializer,
    KitCreateSerializer,
    KitDetailSerializer,
    KitItemCreateSerializer,
    KitItemSerializer,
    KitItemUpdateSerializer,
    KitSerializer,
    KitUpdateSerializer,
)
from catalog.statuses import delete_status, make_default
from households.views import FORBIDDEN, HouseholdScopedView

CREATED_OR_MATCHED = {
    200: OpenApiResponse(
        response=ItemTypeSerializer,
        description=(
            "An entry of this household already went by that name, and it is returned "
            "untouched instead of a second one being created."
        ),
    ),
    201: ItemTypeSerializer,
    403: FORBIDDEN,
}

DEFAULT_STATUS = OpenApiResponse(
    description="The default status cannot be deleted, make another status the default one first."
)

MERGED_OR_RENAMED = {
    200: OpenApiResponse(
        response=ItemTypeSerializer,
        description=(
            "The renamed entry, or the entry that absorbed it when the name was already "
            "taken. The body then carries an id different from the one in the path, and "
            "the one in the path no longer exists."
        ),
    ),
    403: FORBIDDEN,
}


@extend_schema_view(
    post=extend_schema(request=ItemTypeCreateSerializer, responses=CREATED_OR_MATCHED)
)
class ItemTypeListCreateView(HouseholdScopedView, generics.ListCreateAPIView):
    def get_serializer_class(self):
        return ItemTypeCreateSerializer if self.request.method == "POST" else ItemTypeSerializer

    def get_queryset(self):
        return self.household.item_types.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data["name"]
        existing = matching_item_type(self.household.pk, name)
        if existing is None:
            try:
                with transaction.atomic():
                    item_type = serializer.save(household=self.household)
                return Response(ItemTypeSerializer(item_type).data, status=201)
            except IntegrityError:
                existing = matching_item_type(self.household.pk, name)
        return Response(ItemTypeSerializer(existing).data)


@extend_schema_view(delete=extend_schema(responses={204: None, 403: FORBIDDEN}))
class ItemTypeDetailView(HouseholdScopedView, generics.RetrieveDestroyAPIView):
    def get_serializer_class(self):
        return ItemTypeUpdateSerializer if self.request.method == "PATCH" else ItemTypeSerializer

    def get_queryset(self):
        return self.household.item_types.all()

    @extend_schema(request=ItemTypeUpdateSerializer, responses=MERGED_OR_RENAMED)
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        name = serializer.validated_data.pop("name", None)
        if name is not None:
            survivor = rename_item_type(serializer.instance, name)
            if survivor.pk != serializer.instance.pk:
                return Response(ItemTypeSerializer(survivor).data)
        return Response(ItemTypeSerializer(serializer.save()).data)


@extend_schema_view(
    post=extend_schema(
        request=ItemStatusCreateSerializer, responses={201: ItemStatusSerializer, 403: FORBIDDEN}
    )
)
class ItemStatusListCreateView(HouseholdScopedView, generics.ListCreateAPIView):
    def get_serializer_class(self):
        return ItemStatusCreateSerializer if self.request.method == "POST" else ItemStatusSerializer

    def get_queryset(self):
        return self.household.item_statuses.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        status = serializer.save(household=self.household)
        return Response(ItemStatusSerializer(status).data, status=201)


@extend_schema_view(
    delete=extend_schema(responses={204: None, 403: FORBIDDEN, 409: DEFAULT_STATUS})
)
class ItemStatusDetailView(HouseholdScopedView, generics.RetrieveDestroyAPIView):
    def get_serializer_class(self):
        return (
            ItemStatusUpdateSerializer if self.request.method == "PATCH" else ItemStatusSerializer
        )

    def get_queryset(self):
        return self.household.item_statuses.all()

    @extend_schema(
        request=ItemStatusUpdateSerializer,
        responses={200: ItemStatusSerializer, 403: FORBIDDEN},
    )
    @transaction.atomic
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        becomes_default = serializer.validated_data.pop("is_default", False)
        status = serializer.save()
        if becomes_default:
            make_default(status)
        return Response(ItemStatusSerializer(status).data)

    def perform_destroy(self, status):
        delete_status(status)


@extend_schema_view(
    post=extend_schema(request=KitCreateSerializer, responses={201: KitSerializer, 403: FORBIDDEN})
)
class KitListCreateView(HouseholdScopedView, generics.ListCreateAPIView):
    def get_serializer_class(self):
        return KitCreateSerializer if self.request.method == "POST" else KitSerializer

    def get_queryset(self):
        return self.household.kits.all()

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kit = serializer.save(household=self.household)
        return Response(KitSerializer(kit).data, status=201)


@extend_schema_view(delete=extend_schema(responses={204: None, 403: FORBIDDEN}))
class KitDetailView(HouseholdScopedView, generics.RetrieveDestroyAPIView):
    def get_serializer_class(self):
        return KitUpdateSerializer if self.request.method == "PATCH" else KitDetailSerializer

    def get_queryset(self):
        return self.household.kits.prefetch_related("items__item_type", "items__person")

    @extend_schema(
        request=KitUpdateSerializer, responses={200: KitDetailSerializer, 403: FORBIDDEN}
    )
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(KitDetailSerializer(serializer.save()).data)


class KitScopedView(HouseholdScopedView):
    @cached_property
    def kit(self):
        return get_object_or_404(self.household.kits, pk=self.kwargs["kit_id"])

    def get_queryset(self):
        return self.kit.items.select_related("item_type", "person")


@extend_schema_view(
    post=extend_schema(
        request=KitItemCreateSerializer, responses={201: KitItemSerializer, 403: FORBIDDEN}
    )
)
class KitItemListCreateView(KitScopedView, generics.ListCreateAPIView):
    def get_serializer_class(self):
        return KitItemCreateSerializer if self.request.method == "POST" else KitItemSerializer

    def create(self, request, *args, **kwargs):
        kit = self.kit
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        line = serializer.save(kit=kit)
        return Response(KitItemSerializer(line).data, status=201)


@extend_schema_view(delete=extend_schema(responses={204: None, 403: FORBIDDEN}))
class KitItemDetailView(KitScopedView, generics.RetrieveDestroyAPIView):
    def get_serializer_class(self):
        return KitItemUpdateSerializer if self.request.method == "PATCH" else KitItemSerializer

    @extend_schema(
        request=KitItemUpdateSerializer, responses={200: KitItemSerializer, 403: FORBIDDEN}
    )
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(KitItemSerializer(serializer.save()).data)
