from django.contrib import admin

from .models import Specialization


@admin.register(Specialization)
class SpecializationAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "code")
    search_fields = ("name", "code")
