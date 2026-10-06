from django.apps import AppConfig


class PeopleConfig(AppConfig):
    name = 'people'

    def ready(self):
        from people import checks  # noqa: F401 - registers system checks
