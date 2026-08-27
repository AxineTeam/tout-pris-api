from rest_framework import serializers

from catalog.base_catalog import DEFAULT_STATUS_COLOR
from catalog.models import ItemStatus, ItemType, Kit, KitItem
from households.serializers import HouseholdScopedRelation, PersonSerializer


class ItemTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemType
        fields = ["id", "name", "description"]


class ItemTypeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemType
        fields = ["name", "description"]


class ItemTypeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemType
        fields = ["name", "description"]


class ItemStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemStatus
        fields = ["id", "name", "color", "progress", "position", "is_default"]


class ItemStatusCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemStatus
        fields = ["name", "color", "progress"]
        extra_kwargs = {"color": {"default": DEFAULT_STATUS_COLOR}}


class ItemStatusUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemStatus
        fields = ["name", "color", "progress", "is_default"]

    def validate_is_default(self, is_default):
        if not is_default:
            raise serializers.ValidationError(
                "Make another status the default one instead, a household needs one."
            )
        return is_default


class KitItemSerializer(serializers.ModelSerializer):
    item_type = ItemTypeSerializer(read_only=True)
    person = PersonSerializer(read_only=True, allow_null=True)

    class Meta:
        model = KitItem
        fields = ["id", "item_type", "person", "quantity", "note", "position"]


class KitItemCreateSerializer(serializers.ModelSerializer):
    item_type = HouseholdScopedRelation("item_types")
    person = HouseholdScopedRelation("persons", required=False, allow_null=True)

    class Meta:
        model = KitItem
        fields = ["item_type", "person", "quantity", "note"]


class KitItemUpdateSerializer(serializers.ModelSerializer):
    item_type = HouseholdScopedRelation("item_types", required=False)
    person = HouseholdScopedRelation("persons", required=False, allow_null=True)

    class Meta:
        model = KitItem
        fields = ["item_type", "person", "quantity", "note"]


class KitSerializer(serializers.ModelSerializer):
    items = KitItemSerializer(many=True, read_only=True)

    class Meta:
        model = Kit
        fields = ["id", "name", "description", "position", "items"]


class KitCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kit
        fields = ["name", "description"]


class KitUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kit
        fields = ["name", "description"]
