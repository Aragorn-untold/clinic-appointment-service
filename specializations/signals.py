from django.core.cache import cache
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from specializations.models import Specialization


@receiver([post_save, post_delete], sender=Specialization)
def invalidate_specialization_cache(sender, **kwargs):
    cache.delete_pattern("*specializations*")
