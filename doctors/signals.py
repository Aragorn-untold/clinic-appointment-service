from django.core.cache import cache
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from doctors.models import Doctor
from specializations.models import Specialization


@receiver([post_save, post_delete], sender=Doctor)
@receiver([post_save, post_delete], sender=Specialization)
@receiver(m2m_changed, sender=Doctor.specializations.through)
def invalidate_doctor_cache(sender, **kwargs):
    cache.delete_pattern("*doctors*")
