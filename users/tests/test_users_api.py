from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

USER_DETAIL_URL = reverse("users:detail")
USER_CREATE_URL = reverse("users:create")


class UnauthenticatedUser(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_auth_required(self):
        res = self.client.get(USER_DETAIL_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PublicUserApiTests(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()

    def test_create_user_success(self):
        payload = {
            "email": "newuser@test.test",
            "password": "secure_password123",
            "first_name": "Ivan",
            "last_name": "Ivanov",
        }
        res = self.client.post(USER_CREATE_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        user = get_user_model().objects.get(email=payload["email"])
        self.assertTrue(user.check_password(payload["password"]))
        self.assertNotIn("password", res.data)


class AuthenticatedUser(TestCase):
    def setUp(self) -> None:
        self.client = APIClient()
        self.user = get_user_model().objects.create_user(
            email="test@test.test",
            password="test_password"
        )
        self.client.force_authenticate(self.user)

    def test_user_detail(self):
        res = self.client.get(USER_DETAIL_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_update_user_profile(self):
        payload = {
            "first_name": "NewName",
            "last_name": "NewLastName"
        }
        res = self.client.patch(USER_DETAIL_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, payload["first_name"])
        self.assertEqual(self.user.last_name, payload["last_name"])
