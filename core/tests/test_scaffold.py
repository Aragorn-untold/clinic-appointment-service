from django.conf import settings
from django.contrib.auth import get_user_model
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.tests.base import PASSWORD


class SettingsTests(SimpleTestCase):
    def test_custom_user_model(self):
        self.assertEqual(settings.AUTH_USER_MODEL, "users.UserPatient")

    def test_django_filter_is_default_backend(self):
        self.assertIn(
            "django_filters.rest_framework.DjangoFilterBackend",
            settings.REST_FRAMEWORK["DEFAULT_FILTER_BACKENDS"],
        )

    def test_jwt_is_default_authentication(self):
        self.assertIn(
            "rest_framework_simplejwt.authentication.JWTAuthentication",
            settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"],
        )


class SchemaTests(TestCase):
    def test_schema_is_available(self):
        response = self.client.get(reverse("schema"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_swagger_is_available(self):
        response = self.client.get(reverse("swagger"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)


class JWTTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            email="patient@example.com",
            password=PASSWORD,
        )

    def setUp(self):
        self.client = APIClient()

    def test_obtain_token_with_email(self):
        response = self.client.post(
            reverse("token-obtain-pair"),
            {"email": "patient@example.com", "password": PASSWORD},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

    def test_wrong_password_is_rejected(self):
        response = self.client.post(
            reverse("token-obtain-pair"),
            {"email": "patient@example.com", "password": "wrong"},
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_token(self):
        tokens = self.client.post(
            reverse("token-obtain-pair"),
            {"email": "patient@example.com", "password": PASSWORD},
        ).data
        response = self.client.post(
            reverse("token-refresh"),
            {"refresh": tokens["refresh"]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
