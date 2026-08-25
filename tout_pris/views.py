from django.conf import settings
from drf_pydantic import BaseModel
from drf_spectacular.utils import extend_schema
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class Health(BaseModel):
    status: str
    version: str | None
    commit: str | None


@extend_schema(
    responses=Health.drf_serializer,
    summary="Health check",
    tags=["monitoring"],
)
@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    is_administrator = request.user.is_staff
    return Response(
        Health(
            status="ok",
            version=settings.APP_VERSION if is_administrator else None,
            commit=settings.APP_COMMIT if is_administrator else None,
        ).model_dump()
    )
