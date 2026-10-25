from django.urls import reverse
from rest_framework import status

from core.tests.base import BaseTestCase
from specializations.models import Specialization

LIST_URL = reverse("specializations:specialization-list")


def detail_url(pk):
    return reverse("specializations:specialization-detail", args=[pk])


class SpecializationListCacheTests(BaseTestCase):
    """Task O5: the specializations list is cached in Redis and reset by signals.

    queryset.update() skips signals, so it changes the database without
    clearing the cache. A cached response has no .data, so tests read .json().
    """

    def get_names(self):
        res = self.client.get(LIST_URL)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return {item["name"] for item in res.json()}

    def test_list_is_cached(self):
        self.get_names()
        Specialization.objects.filter(pk=self.specialization.pk).update(name="Changed")

        self.assertEqual(self.get_names(), {"Cardiology"})

    def test_retrieve_is_not_cached(self):
        self.client.get(detail_url(self.specialization.pk))
        Specialization.objects.filter(pk=self.specialization.pk).update(name="Changed")

        res = self.client.get(detail_url(self.specialization.pk))

        self.assertEqual(res.json()["name"], "Changed")

    def test_save_clears_cache(self):
        self.get_names()
        self.specialization.name = "Changed"
        self.specialization.save()

        self.assertEqual(self.get_names(), {"Changed"})

    def test_delete_clears_cache(self):
        self.get_names()
        self.specialization.delete()

        self.assertEqual(self.get_names(), set())

    def test_admin_create_clears_cache(self):
        self.get_names()

        res = self.admin_client.post(LIST_URL, {"name": "Neurology", "code": "neurology"})
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        self.assertEqual(self.get_names(), {"Cardiology", "Neurology"})

    def test_cached_list_still_forbids_browser_caching(self):
        self.get_names()

        res = self.client.get(LIST_URL)

        self.assertIn("no-store", res["Cache-Control"])
        self.assertIn("max-age=0", res["Cache-Control"])
