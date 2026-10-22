from django.contrib.auth.models import AnonymousUser
from django.test import SimpleTestCase
from rest_framework.test import APIRequestFactory

from core.permissions import IsAdminOrReadOnly


class StubUser:
    def __init__(self, is_staff):
        self.is_staff = is_staff


class IsAdminOrReadOnlyTests(SimpleTestCase):
    def setUp(self):
        self.factory = APIRequestFactory()
        self.permission = IsAdminOrReadOnly()

    def check(self, method, user):
        request = getattr(self.factory, method)("/")
        request.user = user
        return self.permission.has_permission(request, view=None)

    def test_safe_methods_allowed_for_everyone(self):
        for method in ("get", "head", "options"):
            with self.subTest(method=method):
                self.assertTrue(self.check(method, AnonymousUser()))
                self.assertTrue(self.check(method, StubUser(is_staff=False)))

    def test_unsafe_methods_denied_for_anonymous_and_regular_users(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertFalse(self.check(method, AnonymousUser()))
                self.assertFalse(self.check(method, StubUser(is_staff=False)))

    def test_unsafe_methods_allowed_for_admin(self):
        for method in ("post", "put", "patch", "delete"):
            with self.subTest(method=method):
                self.assertTrue(self.check(method, StubUser(is_staff=True)))
