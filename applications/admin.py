from django.contrib import admin

from .models import Application


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    list_display = ("student", "posting", "status", "submitted_at", "reviewed_at")
    list_filter = ("status",)
    search_fields = ("student__first_name", "student__last_name", "student__student_number", "posting__title")

    def has_delete_permission(self, request, obj=None):  # BR-06
        return False
