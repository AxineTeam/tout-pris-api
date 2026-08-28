from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from catalog.serializers import ItemStatusSerializer, ItemTypeSerializer, KitSerializer
from households.serializers import HouseholdScopedRelation, PersonSerializer
from trips.models import Trip, TripItem, TripParticipant


class TripParticipantSerializer(serializers.ModelSerializer):
    person = PersonSerializer(read_only=True)

    class Meta:
        model = TripParticipant
        fields = ["id", "person"]


class TripParticipantCreateSerializer(serializers.ModelSerializer):
    person = HouseholdScopedRelation("persons")

    class Meta:
        model = TripParticipant
        fields = ["person"]


class TripItemSerializer(serializers.ModelSerializer):
    item_type = ItemTypeSerializer(read_only=True)
    person = PersonSerializer(read_only=True, allow_null=True)
    status = ItemStatusSerializer(read_only=True)
    kits = serializers.SerializerMethodField()

    class Meta:
        model = TripItem
        fields = ["id", "item_type", "person", "quantity", "status", "note", "position", "kits"]

    @extend_schema_field(KitSerializer(many=True))
    def get_kits(self, line):
        tagging = {entry.kit_id: entry.kit for entry in line.item_type.kit_items.all()}
        return KitSerializer(sorted(tagging.values(), key=lambda kit: kit.position), many=True).data


class TripItemCreateSerializer(serializers.ModelSerializer):
    item_type = HouseholdScopedRelation("item_types")
    person = HouseholdScopedRelation("persons", required=False, allow_null=True)
    status = HouseholdScopedRelation("item_statuses", required=False)

    class Meta:
        model = TripItem
        fields = ["item_type", "person", "quantity", "status", "note"]


class TripItemUpdateSerializer(serializers.ModelSerializer):
    item_type = HouseholdScopedRelation("item_types", required=False)
    person = HouseholdScopedRelation("persons", required=False, allow_null=True)
    status = HouseholdScopedRelation("item_statuses", required=False)

    class Meta:
        model = TripItem
        fields = ["item_type", "person", "quantity", "status", "note"]


class TripSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ["id", "name", "date"]


class TripDetailSerializer(serializers.ModelSerializer):
    participants = TripParticipantSerializer(many=True, read_only=True)
    items = TripItemSerializer(many=True, read_only=True)

    class Meta:
        model = Trip
        fields = ["id", "name", "date", "participants", "items"]


class TripCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ["name", "date"]


class TripUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Trip
        fields = ["name", "date"]


class KitInstantiationSerializer(serializers.Serializer):
    kit = HouseholdScopedRelation("kits", pk_field=serializers.IntegerField())
