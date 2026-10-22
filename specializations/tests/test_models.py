from django.db import IntegrityError, transaction
from django.test import TestCase

from specializations.models import Specialization


class SpecializationTests(TestCase):
    def setUp(self):
        self.specialization = Specialization.objects.create(
            name="Cardiology",
            code="cardiology",
        )

    def test_str_returns_name(self):
        self.assertEqual(str(self.specialization), "Cardiology")

    def test_description_is_optional(self):
        self.assertIsNone(self.specialization.description)

    def test_name_and_code_are_unique(self):
        duplicates = (
            {"name": "Cardiology", "code": "cardio-2"},
            {"name": "Cardiology 2", "code": "cardiology"},
        )
        for fields in duplicates:
            with (
                self.subTest(fields=fields),
                self.assertRaises(IntegrityError),
                transaction.atomic(),
            ):
                Specialization.objects.create(**fields)
