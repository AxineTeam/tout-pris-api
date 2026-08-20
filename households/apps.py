from django.apps import AppConfig


class HouseholdsConfig(AppConfig):
    name = "households"

    def ready(self):
        from households import signals  # noqa: F401
