from core.tests.base import BaseTestCase
from specializations.serializers import SpecializationSerializer


class SpecializationSerializerTests(BaseTestCase):
    def test_all_fields(self):
        data = SpecializationSerializer(self.specialization).data
        self.assertEqual(set(data), {"id", "name", "code", "description"})

    def test_valid(self):
        s = SpecializationSerializer(data={"name": "A", "code": "a"})
        self.assertTrue(s.is_valid(), s.errors)

    def test_name_unique(self):
        s = SpecializationSerializer(data={"name": "Cardiology", "code": "b"})
        self.assertFalse(s.is_valid())
        self.assertIn("name", s.errors)

    def test_code_unique(self):
        s = SpecializationSerializer(data={"name": "B", "code": "cardiology"})
        self.assertFalse(s.is_valid())
        self.assertIn("code", s.errors)

    def test_required_fields(self):
        s = SpecializationSerializer(data={})
        self.assertFalse(s.is_valid())
        self.assertEqual({"name", "code"}, set(s.errors))

    def test_invalid_slug(self):
        s = SpecializationSerializer(data={"name": "A", "code": "bad slug!"})
        self.assertFalse(s.is_valid())
        self.assertIn("code", s.errors)

    def test_update_own_values_valid(self):
        s = SpecializationSerializer(
            self.specialization,
            data={"name": "Cardiology", "code": "cardiology"},
        )
        self.assertTrue(s.is_valid(), s.errors)
