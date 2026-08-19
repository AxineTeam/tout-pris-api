from importlib.metadata import version

from ninja import NinjaAPI, Schema

api = NinjaAPI(
    title="Tout Pris API",
    description="Backend API of the Tout Pris project.",
    version=version("tout-pris-back"),
)


class HealthSchema(Schema):
    status: str


@api.get("/health", response=HealthSchema, summary="Health check", tags=["monitoring"])
def health(request):
    return {"status": "ok"}
