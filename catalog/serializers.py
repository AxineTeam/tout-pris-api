from django.utils.translation import gettext_lazy as _
from ordered_model.serializers import OrderedModelSerializer
from rest_framework import serializers

from catalog.base_catalog import DEFAULT_STATUS_COLOR
from catalog.models import ItemStatus, ItemType, Kit, KitItem
from households.serializers import HouseholdScopedRelation, PersonSerializer


class ReorderingSerializer(OrderedModelSerializer):
    """A position moves the entry to that rank, the rest of its group shifting to make room."""

    def validate_position(self, position):
        last = self.instance.get_ordering_queryset().count() - 1
        if not 0 <= position <= last:
            raise serializers.ValidationError(
                _("Give a position from 0 to {last}.").format(last=last)
            )
        return position


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


class ItemStatusUpdateSerializer(ReorderingSerializer):
    class Meta:
        model = ItemStatus
        fields = ["name", "color", "progress", "position", "is_default"]

    def validate_is_default(self, is_default):
        if not is_default:
            raise serializers.ValidationError(
                _("Make another status the default one instead, a household needs one.")
            )
        return is_default


class KitItemSerializer(serializers.ModelSerializer):
    item_type = ItemTypeSerializer(read_only=True)
    person = PersonSerializer(read_only=True, allow_null=True)

    class Meta:
        model = KitItem
        fields = ["id", "item_type", "person", "quantity", "position"]


class KitItemCreateSerializer(serializers.ModelSerializer):
    item_type = HouseholdScopedRelation("item_types")
    person = HouseholdScopedRelation("persons", required=False, allow_null=True)

    class Meta:
        model = KitItem
        fields = ["item_type", "person", "quantity"]


class KitItemUpdateSerializer(ReorderingSerializer):
    item_type = HouseholdScopedRelation("item_types", required=False)
    person = HouseholdScopedRelation("persons", required=False, allow_null=True)

    class Meta:
        model = KitItem
        fields = ["item_type", "person", "quantity", "position"]


class KitSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kit
        fields = ["id", "name", "description", "position"]


class KitDetailSerializer(serializers.ModelSerializer):
    items = KitItemSerializer(many=True, read_only=True)

    class Meta:
        model = Kit
        fields = ["id", "name", "description", "position", "items"]


class KitCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Kit
        fields = ["name", "description"]


class KitUpdateSerializer(ReorderingSerializer):
    class Meta:
        model = Kit
        fields = ["name", "description", "position"]
