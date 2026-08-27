from django.http import Http404
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from households.models import Household, HouseholdMember, Invitation, Person


class HouseholdScopedRelation(serializers.PrimaryKeyRelatedField):
    def __init__(self, collection, **kwargs):
        self.collection = collection
        super().__init__(**kwargs)

    def get_queryset(self):
        return getattr(self.context["household"], self.collection).all()

    def fail(self, key, **kwargs):
        if key == "does_not_exist":
            raise Http404
        super().fail(key, **kwargs)


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


class HouseholdUpdateSerializer(serializers.ModelSerializer):
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


class PersonUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["name"]


class MemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)

    class Meta:
        model = HouseholdMember
        fields = ["id", "user", "email", "role"]
        read_only_fields = ["user", "role"]


class MemberUpdateSerializer(serializers.ModelSerializer):
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
