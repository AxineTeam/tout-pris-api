from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from households.models import Household, Invitation


class HouseholdSerializer(serializers.ModelSerializer):
    personal = serializers.SerializerMethodField()

    class Meta:
        model = Household
        fields = ["id", "name", "personal"]

    @extend_schema_field(serializers.BooleanField)
    def get_personal(self, household):
        return household.personal_of_id is not None


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ["id", "email", "person", "created_at", "expires_at"]


class InvitationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ["email", "person"]

    def get_fields(self):
        fields = super().get_fields()
        household = self.context.get("household")
        if household:
            fields["person"].queryset = household.persons.all()
        return fields


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
