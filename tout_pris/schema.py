from allauth.headless.spec.internal.schema import get_schema
from django.core.exceptions import ImproperlyConfigured
from drf_spectacular.generators import SchemaGenerator

MERGED_COMPONENT_SECTIONS = ("schemas", "parameters", "examples", "responses", "securitySchemes")


class HeadlessAwareSchemaGenerator(SchemaGenerator):
    def get_schema(self, request=None, public=False):
        result = super().get_schema(request=request, public=public)
        headless = get_schema()
        merge_without_overwriting(result.setdefault("paths", {}), headless["paths"], "paths")
        components = result.setdefault("components", {})
        for section in MERGED_COMPONENT_SECTIONS:
            entries = headless.get("components", {}).get(section)
            if entries:
                merge_without_overwriting(components.setdefault(section, {}), entries, section)
        result.setdefault("tags", []).extend(headless.get("tags", []))
        return result


def merge_without_overwriting(target, additions, section):
    conflicts = sorted(set(target) & set(additions))
    if conflicts:
        raise ImproperlyConfigured(
            f"django-allauth and the API both describe {section} {conflicts} in the schema"
        )
    target.update(additions)
