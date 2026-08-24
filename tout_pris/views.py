from django.conf import settings
from drf_pydantic import BaseModel
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class Health(BaseModel):
    status: str
    version: str
    commit: str


@extend_schema(
    responses=Health.drf_serializer,
    summary="Health check",
    tags=["monitoring"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    return Response(
        Health(
            status="ok",
            version=settings.SPECTACULAR_SETTINGS["VERSION"],
            commit=settings.GIT_COMMIT,
        ).model_dump()
    )
