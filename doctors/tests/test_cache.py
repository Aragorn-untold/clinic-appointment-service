from django.urls import reverse
from rest_framework import status

from core.tests.base import BaseTestCase
from doctors.models import Doctor
from specializations.models import Specialization

DOCTOR_LIST_URL = reverse("doctors:doctor-list")


def doctor_detail_url(doctor_id):
    return reverse("doctors:doctor-detail", args=[doctor_id])


class DoctorListCacheTests(BaseTestCase):
    """Task O5: the doctors list is cached in Redis and reset by signals.

    queryset.update() skips signals, so it changes the database without
    clearing the cache. A cached response has no .data, so tests read .json().
    """

    def get_list(self, **params):
        res = self.client.get(DOCTOR_LIST_URL, params)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        return res.json()

    def find_doctor(self, doctors, doctor_id):
        return next(doctor for doctor in doctors if doctor["id"] == doctor_id)

    def test_list_is_cached(self):
        self.get_list()
        Doctor.objects.filter(pk=self.doctor.pk).update(last_name="Changed")

        doctor = self.find_doctor(self.get_list(), self.doctor.pk)

        self.assertEqual(doctor["last_name"], "Kovalenko")

    def test_retrieve_is_not_cached(self):
        self.client.get(doctor_detail_url(self.doctor.pk))
        Doctor.objects.filter(pk=self.doctor.pk).update(last_name="Changed")

        res = self.client.get(doctor_detail_url(self.doctor.pk))

        self.assertEqual(res.json()["last_name"], "Changed")

    def test_filtered_list_is_cached_separately(self):
        other = Specialization.objects.create(name="Neurology", code="neurology")
        other_doctor = Doctor.objects.create(first_name="Petro", last_name="Shevchenko", price_per_visit="500.00")
        other_doctor.specializations.add(other)

        filtered = self.get_list(specialization=self.specialization.code)
        unfiltered = self.get_list()

        self.assertEqual({doctor["id"] for doctor in filtered}, {self.doctor.pk})
        self.assertEqual({doctor["id"] for doctor in unfiltered}, {self.doctor.pk, other_doctor.pk})

    def test_doctor_save_clears_cache(self):
        self.get_list()
        self.doctor.last_name = "Changed"
        self.doctor.save()

        doctor = self.find_doctor(self.get_list(), self.doctor.pk)

        self.assertEqual(doctor["last_name"], "Changed")

    def test_doctor_delete_clears_cache(self):
        doctor = Doctor.objects.create(first_name="Petro", last_name="Shevchenko", price_per_visit="500.00")
        doctor_id = doctor.pk
        self.get_list()
        doctor.delete()

        ids = {item["id"] for item in self.get_list()}

        self.assertNotIn(doctor_id, ids)

    def test_admin_create_clears_cache(self):
        self.get_list()
        payload = {
            "first_name": "Bob",
            "last_name": "Bobovich",
            "specializations": [self.specialization.code],
            "price_per_visit": "150.00",
        }
        res = self.admin_client.post(DOCTOR_LIST_URL, payload, format="json")
        self.assertEqual(res.status_code, status.HTTP_201_CREATED)

        ids = {doctor["id"] for doctor in self.get_list()}

        self.assertIn(res.data["id"], ids)

    def test_specialization_change_clears_cache(self):
        self.get_list()
        self.specialization.code = "cardio"
        self.specialization.save()

        doctor = self.find_doctor(self.get_list(), self.doctor.pk)

        self.assertEqual(doctor["specializations"], ["cardio"])

    def test_doctor_specializations_change_clears_cache(self):
        self.get_list()
        neurology = Specialization.objects.create(name="Neurology", code="neurology")
        self.doctor.specializations.add(neurology)

        doctor = self.find_doctor(self.get_list(), self.doctor.pk)

        self.assertEqual(set(doctor["specializations"]), {"cardiology", "neurology"})

    def test_cached_list_still_forbids_browser_caching(self):
        self.get_list()

        res = self.client.get(DOCTOR_LIST_URL)

        self.assertIn("no-store", res["Cache-Control"])
        self.assertIn("max-age=0", res["Cache-Control"])
