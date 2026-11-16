from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField

from .models import Company, SchoolCoordinator, Student, User


class UserCreationAdminForm(forms.ModelForm):
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = ("email", "role")

    def clean_password2(self):
        p1, p2 = self.cleaned_data.get("password1"), self.cleaned_data.get("password2")
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Passwords don't match.")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = user.email.lower()
        user.set_password(self.cleaned_data["password1"])
        if commit:
            user.save()
        return user


class UserChangeAdminForm(forms.ModelForm):
    password = ReadOnlyPasswordHashField()

    class Meta:
        model = User
        fields = "__all__"


class StudentInline(admin.StackedInline):
    model = Student
    fk_name = "user"
    can_delete = False


class CompanyInline(admin.StackedInline):
    model = Company
    fk_name = "user"
    can_delete = False


class CoordinatorInline(admin.StackedInline):
    model = SchoolCoordinator
    fk_name = "user"
    can_delete = False


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    form = UserChangeAdminForm
    add_form = UserCreationAdminForm
    list_display = ("email", "role", "account_status", "locked_until", "created_at", "last_login")
    list_filter = ("role", "account_status", "is_staff")
    search_fields = ("email",)
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "last_login")
    actions = ["deactivate_accounts", "activate_accounts", "unlock_accounts"]
    fieldsets = (
        (None, {"fields": ("email", "password", "role")}),
        ("Status", {"fields": ("account_status", "failed_login_count", "locked_until")}),
        ("Admin access", {"fields": ("is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("created_at", "last_login")}),
    )
    add_fieldsets = ((None, {"classes": ("wide",), "fields": ("email", "role", "password1", "password2")}),)
    filter_horizontal = ("groups", "user_permissions")

    def get_inlines(self, request, obj):
        if obj is None:
            return []
        return {
            User.Role.STUDENT: [StudentInline],
            User.Role.COMPANY: [CompanyInline],
            User.Role.COORDINATOR: [CoordinatorInline],
        }.get(obj.role, [])

    # BR-06: records are never physically deleted — deactivate instead.
    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Deactivate selected accounts")
    def deactivate_accounts(self, request, queryset):
        queryset.update(account_status=User.AccountStatus.DEACTIVATED)

    @admin.action(description="Activate selected accounts")
    def activate_accounts(self, request, queryset):
        queryset.update(account_status=User.AccountStatus.ACTIVE)

    @admin.action(description="Unlock selected accounts")
    def unlock_accounts(self, request, queryset):
        queryset.update(failed_login_count=0, locked_until=None)


class NoDeleteAdmin(admin.ModelAdmin):
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Student)
class StudentAdmin(NoDeleteAdmin):
    list_display = ("student_number", "last_name", "first_name", "program", "year_level", "coordinator")
    list_filter = ("program", "year_level", "coordinator")
    search_fields = ("student_number", "first_name", "last_name", "user__email")


@admin.register(Company)
class CompanyAdmin(NoDeleteAdmin):
    list_display = ("company_name", "city", "industry", "verification_status", "verified_by")
    list_filter = ("verification_status", "city")
    search_fields = ("company_name", "user__email")


@admin.register(SchoolCoordinator)
class SchoolCoordinatorAdmin(NoDeleteAdmin):
    list_display = ("last_name", "first_name", "department", "contact_number")
    search_fields = ("first_name", "last_name", "user__email")
