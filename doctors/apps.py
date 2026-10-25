from django.apps import AppConfig


class DoctorsConfig(AppConfig):
    name = "doctors"

    def ready(self):
        from doctors import signals  # noqa
