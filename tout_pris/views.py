from django.conf import settings
from drf_pydantic import BaseModel
from drf_spectacular.utils import extend_schema
from pydantic import Field
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class Health(BaseModel):
    status: str
    version: str = Field(
        description="Git ref the running image was built from, the tag on a release and the "
        "branch otherwise."
    )
    commit: str | None = Field(
        description="Short commit the running image was built from. Null unless the caller "
        "is an administrator."
    )


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
            version=settings.APP_VERSION,
            commit=settings.APP_COMMIT if request.user.is_staff else None,
        ).model_dump()
    )
