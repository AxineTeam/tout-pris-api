from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class HealthSerializer(serializers.Serializer):
    status = serializers.CharField()


@extend_schema(
    responses=HealthSerializer,
    summary="Health check",
    tags=["monitoring"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response({"status": "ok"})
