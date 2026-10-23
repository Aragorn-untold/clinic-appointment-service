from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from core.tests.base import PASSWORD, BaseTestCase

USER_DETAIL_URL = reverse("users:detail")
USER_CREATE_URL = reverse("users:create")
TOKEN_URL = reverse("users:token_obtain_pair")
TOKEN_REFRESH_URL = reverse("users:token_refresh")


class UnauthenticatedUser(BaseTestCase):
    def test_auth_required(self):
        res = self.client.get(USER_DETAIL_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class AuthenticatedUser(BaseTestCase):
    def test_user_detail(self):
        res = self.auth_client.get(USER_DETAIL_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_update_user_profile(self):
        payload = {"first_name": "NewName", "last_name": "NewLastName"}
        res = self.auth_client.patch(USER_DETAIL_URL, payload)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.first_name, payload["first_name"])
        self.assertEqual(self.user.last_name, payload["last_name"])


class PublicUserApiTests(BaseTestCase):
    def test_create_user_success(self):
        payload = {
            "email": "new_patient@example.com",
            "password": "SecurePassword123!",
            "first_name": "Anna",
            "last_name": "Koval",
        }
        res = self.client.post(USER_CREATE_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        user = get_user_model().objects.get(email=payload["email"])
        self.assertTrue(user.check_password(payload["password"]))
        self.assertNotIn("password", res.data)

    def test_create_user_weak_password_fails(self):
        payload = {
            "email": "weak_password@example.com",
            "password": "12345",  # Простой пароль не пройдет валідатор
            "first_name": "Test",
        }
        res = self.client.post(USER_CREATE_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class JWTAuthenticationApiTests(BaseTestCase):
    def test_obtain_token_and_refresh(self):
        payload = {
            "email": self.user.email,
            "password": PASSWORD,
        }

        res = self.client.post(TOKEN_URL, payload)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn("access", res.data)
        self.assertIn("refresh", res.data)

        refresh_token = res.data["refresh"]

        # 2. Обновление токена (refresh)
        res_refresh = self.client.post(TOKEN_REFRESH_URL, {"refresh": refresh_token})
        self.assertEqual(res_refresh.status_code, status.HTTP_200_OK)
        self.assertIn("access", res_refresh.data)

    def test_request_with_custom_authorize_header_success(self):
        token_res = self.client.post(TOKEN_URL, {"email": self.user.email, "password": PASSWORD})
        access_token = token_res.data["access"]

        auth_client = APIClient()
        auth_client.credentials(HTTP_AUTHORIZE=f"Bearer {access_token}")

        res = auth_client.get(USER_DETAIL_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["email"], self.user.email)

    def test_request_with_old_authorization_header_fails(self):
        token_res = self.client.post(TOKEN_URL, {"email": self.user.email, "password": PASSWORD})
        access_token = token_res.data["access"]

        auth_client = APIClient()
        auth_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

        res = auth_client.get(USER_DETAIL_URL)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
