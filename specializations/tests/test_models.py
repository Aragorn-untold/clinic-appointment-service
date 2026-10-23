from django.db import IntegrityError, transaction

from core.tests.base import BaseTestCase
from specializations.models import Specialization


class SpecializationTests(BaseTestCase):
    def test_str_returns_name(self):
        self.assertEqual(str(self.specialization), "Cardiology")

    def test_description_is_optional(self):
        self.assertEqual(self.specialization.description, "")

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
