from collections.abc import Mapping

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from households.models import Household, HouseholdMember, Invitation, Person


class PartialWriteSerializer(serializers.ModelSerializer):
    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            data = {field: value for field, value in data.items() if value is not None}
        return super().to_internal_value(data)


class HouseholdSerializer(serializers.ModelSerializer):
    personal = serializers.SerializerMethodField()

    class Meta:
        model = Household
        fields = ["id", "name", "personal"]

    @extend_schema_field(serializers.BooleanField)
    def get_personal(self, household):
        return household.personal_of_id is not None


class HouseholdCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Household
        fields = ["name"]


class HouseholdUpdateSerializer(PartialWriteSerializer):
    class Meta:
        model = Household
        fields = ["name"]


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["id", "name", "user"]
        read_only_fields = ["user"]


class PersonCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["name"]


class PersonUpdateSerializer(PartialWriteSerializer):
    class Meta:
        model = Person
        fields = ["name"]


class MemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = HouseholdMember
        fields = ["id", "user", "email", "role"]
        read_only_fields = ["user", "role"]


class MemberUpdateSerializer(PartialWriteSerializer):
    class Meta:
        model = HouseholdMember
        fields = ["role"]


class InvitationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ["id", "email", "created_at", "expires_at"]


class InvitationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Invitation
        fields = ["email"]


class InvitationAcceptSerializer(serializers.Serializer):
    token = serializers.CharField()
