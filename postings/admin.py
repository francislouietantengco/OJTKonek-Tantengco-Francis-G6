from django.contrib import admin

from .models import Field, OjtPosting


@admin.register(Field)
class FieldAdmin(admin.ModelAdmin):
    list_display = ("field_name", "description")
    search_fields = ("field_name",)


@admin.register(OjtPosting)
class OjtPostingAdmin(admin.ModelAdmin):
    list_display = ("title", "company", "field", "location", "duration_weeks", "slots", "application_deadline", "status")
    list_filter = ("status", "field")
    search_fields = ("title", "company__company_name", "location")

    def has_delete_permission(self, request, obj=None):  # BR-06
        return False
