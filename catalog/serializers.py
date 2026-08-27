from rest_framework import serializers

from catalog.base_catalog import DEFAULT_STATUS_COLOR
from catalog.models import ItemStatus, ItemType
from households.serializers import PartialWriteSerializer


class ItemTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemType
        fields = ["id", "name", "description"]


class ItemTypeCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = ItemType
        fields = ["name", "description"]


class ItemTypeUpdateSerializer(PartialWriteSerializer):
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


class ItemStatusUpdateSerializer(PartialWriteSerializer):
    class Meta:
        model = ItemStatus
        fields = ["name", "color", "progress", "is_default"]

    def validate_is_default(self, is_default):
        if not is_default:
            raise serializers.ValidationError(
                "Make another status the default one instead, a household needs one."
            )
        return is_default
