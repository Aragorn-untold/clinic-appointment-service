from datetime import time, timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from doctor_slots.models import DoctorSlot
from doctors.models import Doctor
from doctors.services import generate_slots
from specializations.models import Specialization

SPECIALIZATIONS = [
    {"code": "cardiology", "name": "Cardiology"},
    {"code": "neurology", "name": "Neurology"},
    {"code": "pediatrics", "name": "Pediatrics"},
    {"code": "family-medicine", "name": "Family medicine"},
]
DOCTORS = [
    {
        "first_name": "Olena",
        "last_name": "Kovalenko",
        "price_per_visit": Decimal("800.00"),
        "specializations": ["cardiology"],
    },
    {
        "first_name": "Andrii",
        "last_name": "Melnyk",
        "price_per_visit": Decimal("950.00"),
        "specializations": ["neurology"],
    },
    {
        "first_name": "Iryna",
        "last_name": "Bondarenko",
        "price_per_visit": Decimal("600.00"),
        "specializations": ["pediatrics", "family-medicine"],
    },
    {
        "first_name": "Taras",
        "last_name": "Shevchuk",
        "price_per_visit": Decimal("700.00"),
        "specializations": ["family-medicine"],
    },
]

DEMO_PASSWORD = "demo-password-123"
DEMO_USERS = [
    {
        "email": "admin@clinic.demo",
        "first_name": "Admin",
        "last_name": "Demo",
        "is_admin": True,
    },
    {
        "email": "patient@clinic.demo",
        "first_name": "Maria",
        "last_name": "Hrytsenko",
        "is_admin": False,
    },
]

SLOT_DAYS = 5  # working days ahead, starting tomorrow
WORKDAY_START = time(9, 0)
WORKDAY_END = time(13, 0)
SLOT_LENGTH_MINUTES = 30


class Command(BaseCommand):
    help = (
        "Populate the database with demo data: specializations, doctors, "
        "upcoming slots and demo users. Safe to run repeatedly: existing "
        "records are kept and nothing is duplicated."
    )

    @transaction.atomic
    def handle(self, *args, **options):
        specializations, created_specs = self._seed_specializations()
        doctors, created_doctors = self._seed_doctors(specializations)
        created_users = self._seed_users()
        created_slots = self._seed_slots(doctors)

        self.stdout.write(self.style.SUCCESS("Demo data is ready."))
        self.stdout.write(f"  Specializations created: {created_specs}")
        self.stdout.write(f"  Doctors created: {created_doctors}")
        self.stdout.write(f"  Users created: {created_users}")
        self.stdout.write(f"  Slots created: {created_slots}")
        self.stdout.write("Demo accounts (password: %s):" % DEMO_PASSWORD)
        for user in DEMO_USERS:
            role = "admin" if user["is_admin"] else "patient"
            self.stdout.write(f"  {user['email']} ({role})")

    def _seed_specializations(self):
        by_code = {}
        created_count = 0
        for data in SPECIALIZATIONS:
            specialization, created = Specialization.objects.get_or_create(
                code=data["code"],
                defaults={"name": data["name"]},
            )
            by_code[specialization.code] = specialization
            created_count += created
        return by_code, created_count

    def _seed_doctors(self, specializations):
        doctors = []
        created_count = 0
        for data in DOCTORS:
            doctor, created = Doctor.objects.get_or_create(
                first_name=data["first_name"],
                last_name=data["last_name"],
                defaults={"price_per_visit": data["price_per_visit"]},
            )
            doctor.specializations.add(*(specializations[code] for code in data["specializations"]))
            doctors.append(doctor)
            created_count += created
        return doctors, created_count

    def _seed_users(self):
        user_model = get_user_model()
        created_count = 0
        for data in DEMO_USERS:
            if user_model.objects.filter(email=data["email"]).exists():
                continue
            create = user_model.objects.create_superuser if data["is_admin"] else user_model.objects.create_user
            create(
                email=data["email"],
                password=DEMO_PASSWORD,
                first_name=data["first_name"],
                last_name=data["last_name"],
            )
            created_count += 1
        return created_count

    def _seed_slots(self, doctors):
        workdays = self._upcoming_workdays(SLOT_DAYS)
        period_start = timezone.make_aware(timezone.datetime.combine(workdays[0], WORKDAY_START))
        period_end = timezone.make_aware(timezone.datetime.combine(workdays[-1], WORKDAY_END))

        new_slots = []
        for doctor in doctors:
            existing = list(
                DoctorSlot.objects.filter(doctor=doctor, start__lt=period_end, end__gt=period_start).values_list(
                    "start", "end"
                )
            )
            for day in workdays:
                for start, end in generate_slots(day, WORKDAY_START, WORKDAY_END, SLOT_LENGTH_MINUTES):
                    start = timezone.make_aware(start)
                    end = timezone.make_aware(end)
                    overlaps = any(start < ex_end and end > ex_start for ex_start, ex_end in existing)
                    if not overlaps:
                        new_slots.append(DoctorSlot(doctor=doctor, start=start, end=end))

        DoctorSlot.objects.bulk_create(new_slots)
        return len(new_slots)

    @staticmethod
    def _upcoming_workdays(count):
        days = []
        day = timezone.localdate()
        while len(days) < count:
            day += timedelta(days=1)
            if day.weekday() < 5:  # Monday-Friday
                days.append(day)
        return days
