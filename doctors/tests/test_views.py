from decimal import Decimal

from django.urls import reverse
from rest_framework import status

from core.tests.base import BaseTestCase
from doctors.models import Doctor
from specializations.models import Specialization

DOCTOR_LIST_URL = reverse("doctors:doctor-list")


def doctor_detail_url(doctor_id):
    return reverse("doctors:doctor-detail", args=[doctor_id])


class DoctorApiTests(BaseTestCase):
    @classmethod
    def setUpTestData(cls) -> None:
        super().setUpTestData()
        cls.specialization_2 = Specialization.objects.create(name="pediatrics", code="pediatrics")
        cls.specialization_3 = Specialization.objects.create(name="Family doctor", code="family-medicine")
        cls.doctor_2 = Doctor.objects.create(
            first_name="Ms test 2", last_name="testtest", price_per_visit=Decimal("10.45")
        )
        cls.doctor_2.specializations.set([cls.specialization_2, cls.specialization_3])

    def doctor_payload(self, **overrides):
        payload = {
            "first_name": "Bob",
            "last_name": "Bobovich",
            "specializations": [self.specialization.code, self.specialization_2.code],
            "price_per_visit": "150.05",
        }
        payload.update(overrides)
        return payload

    def test_anonymous_can_list_doctors(self):
        res = self.client.get(DOCTOR_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_anonymous_cannot_create_doctor(self):
        res = self.client.post(DOCTOR_LIST_URL, self.doctor_payload(), format="json")

        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertFalse(Doctor.objects.filter(last_name="Bobovich").exists())

    def test_patient_cannot_create_doctor(self):
        res = self.auth_client.post(DOCTOR_LIST_URL, self.doctor_payload(), format="json")

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertFalse(Doctor.objects.filter(last_name="Bobovich").exists())

    def test_admin_can_create_doctor(self):
        payload = self.doctor_payload()

        res = self.admin_client.post(DOCTOR_LIST_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doctor = Doctor.objects.get(pk=res.data["id"])
        self.assertEqual(doctor.first_name, payload["first_name"])
        self.assertEqual(doctor.last_name, payload["last_name"])
        self.assertEqual(doctor.price_per_visit, Decimal("150.05"))
        self.assertEqual(
            set(doctor.specializations.values_list("code", flat=True)),
            set(payload["specializations"]),
        )

    def test_filter_doctors_by_specialization_id(self):
        res = self.client.get(DOCTOR_LIST_URL, {"specialization": self.specialization.id})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = {doctor["id"] for doctor in res.data}
        self.assertEqual(returned_ids, {self.doctor.id})

    def test_filter_doctors_by_specialization_code(self):
        res = self.client.get(DOCTOR_LIST_URL, {"specialization": self.specialization.code})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = {doctor["id"] for doctor in res.data}
        self.assertEqual(returned_ids, {self.doctor.id})

    def test_filter_by_specialization_code_with_hyphen(self):
        res = self.client.get(DOCTOR_LIST_URL, {"specialization": self.specialization_3.code})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        returned_ids = {doctor["id"] for doctor in res.data}
        self.assertEqual(returned_ids, {self.doctor_2.id})

    def test_filter_doctors_by_nonexistent_specialization(self):
        res = self.client.get(DOCTOR_LIST_URL, {"specialization": "astrology"})

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data, [])

    def test_create_doctor_with_nonexistent_specialization(self):
        payload = self.doctor_payload(specializations=["astrology"])

        res = self.admin_client.post(DOCTOR_LIST_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("specializations", res.data)
        self.assertFalse(Doctor.objects.filter(last_name="Bobovich").exists())

    def test_create_doctor_with_negative_price(self):
        payload = self.doctor_payload(price_per_visit="-0.01")

        res = self.admin_client.post(DOCTOR_LIST_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price_per_visit", res.data)
        self.assertFalse(Doctor.objects.filter(last_name="Bobovich").exists())

    def test_create_doctor_with_zero_price(self):
        payload = self.doctor_payload(price_per_visit="0.00")

        res = self.admin_client.post(DOCTOR_LIST_URL, payload, format="json")

        self.assertEqual(res.status_code, status.HTTP_201_CREATED)
        doctor = Doctor.objects.get(pk=res.data["id"])
        self.assertEqual(doctor.price_per_visit, Decimal("0.00"))

    def test_admin_cannot_update_price_to_negative(self):
        res = self.admin_client.patch(
            doctor_detail_url(self.doctor_2.id),
            {"price_per_visit": "-100.00"},
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("price_per_visit", res.data)
        self.doctor_2.refresh_from_db()
        self.assertEqual(self.doctor_2.price_per_visit, Decimal("10.45"))

    def test_list_returns_specializations_as_codes(self):
        res = self.client.get(DOCTOR_LIST_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        doctor_data = next(d for d in res.data if d["id"] == self.doctor_2.id)
        self.assertEqual(
            set(doctor_data["specializations"]),
            {self.specialization_2.code, self.specialization_3.code},
        )

    def test_retrieve_doctor(self):
        res = self.client.get(doctor_detail_url(self.doctor.id))

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data["id"], self.doctor.id)
        self.assertEqual(res.data["last_name"], self.doctor.last_name)

    def test_admin_can_partially_update_doctor(self):
        res = self.admin_client.patch(
            doctor_detail_url(self.doctor_2.id),
            {"price_per_visit": "999.99"},
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.doctor_2.refresh_from_db()
        self.assertEqual(self.doctor_2.price_per_visit, Decimal("999.99"))

    def test_admin_can_replace_specializations(self):
        res = self.admin_client.patch(
            doctor_detail_url(self.doctor_2.id),
            {"specializations": [self.specialization.code]},
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(
            set(self.doctor_2.specializations.values_list("code", flat=True)),
            {self.specialization.code},
        )

    def test_patient_cannot_update_doctor(self):
        res = self.auth_client.patch(
            doctor_detail_url(self.doctor_2.id),
            {"price_per_visit": "1.00"},
            format="json",
        )

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.doctor_2.refresh_from_db()
        self.assertNotEqual(self.doctor_2.price_per_visit, Decimal("1.00"))

    def test_admin_can_delete_doctor(self):
        # doctor_2 has no slots or appointments; self.doctor from BaseTestCase does
        res = self.admin_client.delete(doctor_detail_url(self.doctor_2.id))

        self.assertEqual(res.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Doctor.objects.filter(pk=self.doctor_2.id).exists())

    def test_patient_cannot_delete_doctor(self):
        res = self.auth_client.delete(doctor_detail_url(self.doctor_2.id))

        self.assertEqual(res.status_code, status.HTTP_403_FORBIDDEN)
        self.assertTrue(Doctor.objects.filter(pk=self.doctor_2.id).exists())
