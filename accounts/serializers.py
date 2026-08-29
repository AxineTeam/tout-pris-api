from rest_framework import serializers

from accounts.models import User


class MeSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "email", "language"]


class MeUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["language"]
