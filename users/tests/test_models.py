from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import TestCase

PASSWORD = "test-password-123"


class UserPatientTests(TestCase):
    def setUp(self):
        self.user_model = get_user_model()

    def test_create_user_with_email(self):
        user = self.user_model.objects.create_user(
            email="patient@EXAMPLE.com",
            password=PASSWORD,
        )
        self.assertEqual(user.email, "patient@example.com")
        self.assertTrue(user.check_password(PASSWORD))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)

    def test_email_is_login_field_and_no_username(self):
        self.assertEqual(self.user_model.USERNAME_FIELD, "email")
        self.assertIsNone(self.user_model.username)

    def test_create_user_without_email_raises(self):
        with self.assertRaises(ValueError):
            self.user_model.objects.create_user(email="", password=PASSWORD)

    def test_email_is_unique(self):
        self.user_model.objects.create_user(
            email="patient@example.com", password=PASSWORD
        )
        with self.assertRaises(IntegrityError):
            self.user_model.objects.create_user(
                email="patient@example.com", password=PASSWORD
            )

    def test_create_superuser(self):
        admin = self.user_model.objects.create_superuser(
            email="admin@example.com",
            password=PASSWORD,
        )
        self.assertTrue(admin.is_staff)
        self.assertTrue(admin.is_superuser)

    def test_create_superuser_with_wrong_flags_raises(self):
        for flag in ("is_staff", "is_superuser"):
            with self.subTest(flag=flag), self.assertRaises(ValueError):
                self.user_model.objects.create_superuser(
                    email=f"{flag}@example.com",
                    password=PASSWORD,
                    **{flag: False},
                )
