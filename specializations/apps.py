from django.apps import AppConfig


class SpecializationsConfig(AppConfig):
    name = "specializations"

    def ready(self):
        from specializations import signals  # noqa
