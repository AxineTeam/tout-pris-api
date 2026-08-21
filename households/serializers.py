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

    def validate_person(self, person):
        if person.household_id != self.context["household"].pk:
            raise serializers.ValidationError("This person belongs to another household.")
        return person


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
