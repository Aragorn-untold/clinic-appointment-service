from django.urls import reverse
from rest_framework import status

from core.tests.base import BaseTestCase
from specializations.models import Specialization

LIST_URL = reverse("specializations:specialization-list")
PAYLOAD = {"name": "Neurology", "code": "neurology"}


def detail_url(pk):
    return reverse("specializations:specialization-detail", args=[pk])


class SpecializationApiTests(BaseTestCase):
    def test_anonymous_can_list(self):
        res = self.client.get(LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_anonymous_can_retrieve(self):
        res = self.client.get(detail_url(self.specialization.id))
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["code"], "cardiology")

    def test_create_anonymous_denied(self):
        res = self.client.post(LIST_URL, PAYLOAD)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_update_anonymous_denied(self):
        res = self.client.patch(detail_url(self.specialization.id), {"description": "x"})
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_delete_anonymous_denied(self):
        res = self.client.delete(detail_url(self.specialization.id))
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_regular_user_cannot_create(self):
        res = self.auth_client.post(LIST_URL, PAYLOAD)
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_update(self):
        res = self.auth_client.patch(detail_url(self.specialization.id), {"description": "x"})
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_regular_user_cannot_delete(self):
        res = self.auth_client.delete(detail_url(self.specialization.id))
        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create(self):
        res = self.admin_client.post(LIST_URL, PAYLOAD)
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        self.assertTrue(Specialization.objects.filter(code="neurology").exists())

    def test_admin_can_put(self):
        res = self.admin_client.put(
            detail_url(self.specialization.id),
            {"name": "Cardio", "code": "cardio", "description": "New"},
        )
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.specialization.refresh_from_db()
        self.assertEqual(self.specialization.code, "cardio")

    def test_admin_can_patch(self):
        res = self.admin_client.patch(detail_url(self.specialization.id), {"description": "Updated"})
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.specialization.refresh_from_db()
        self.assertEqual(self.specialization.description, "Updated")

    def test_admin_can_delete(self):
        spec = Specialization.objects.create(name="Temp", code="temp")
        res = self.admin_client.delete(detail_url(spec.id))
        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Specialization.objects.filter(id=spec.id).exists())

    def test_duplicate_name_rejected(self):
        res = self.admin_client.post(LIST_URL, {"name": "Cardiology", "code": "other"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duplicate_code_rejected(self):
        res = self.admin_client.post(LIST_URL, {"name": "Other", "code": "cardiology"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_slug_rejected(self):
        res = self.admin_client.post(LIST_URL, {"name": "Bad", "code": "not a slug!"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_name_required(self):
        res = self.admin_client.post(LIST_URL, {"code": "abc"})
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
