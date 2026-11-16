from django import forms
from django.contrib.auth import authenticate
from django.contrib.auth.forms import UserCreationForm
from django.db import transaction

from .models import Company, SchoolCoordinator, Student, User


class StyledFormMixin:
    """Adds a CSS class to every widget so the templates stay simple."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "input")


def clean_unique_email(email, exclude_pk=None):
    """BR-01: every account must have a unique email address."""
    email = email.strip().lower()
    qs = User.objects.filter(email__iexact=email)
    if exclude_pk:
        qs = qs.exclude(pk=exclude_pk)
    if qs.exists():
        raise forms.ValidationError("An account with this email already exists.")
    return email


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------
class BaseRegistrationForm(StyledFormMixin, UserCreationForm):
    """
    UserCreationForm already validates that password1 and password2 match,
    runs the password validators (BR-02) and hashes the password.
    """

    email = forms.EmailField(max_length=100, required=True)

    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        return clean_unique_email(self.cleaned_data["email"])


class StudentRegistrationForm(BaseRegistrationForm):
    first_name = forms.CharField(max_length=50)
    last_name = forms.CharField(max_length=50)
    student_number = forms.RegexField(
        regex=r"^\d{2}-\d{4}-\d{3}$",
        max_length=15,
        help_text="Format: 23-7573-680",
        error_messages={"invalid": "Use the format 23-7573-680."},
    )
    program = forms.ChoiceField(choices=Student.Program.choices)
    year_level = forms.TypedChoiceField(choices=[(i, f"Year {i}") for i in range(1, 5)], coerce=int)
    coordinator = forms.ModelChoiceField(
        queryset=SchoolCoordinator.objects.filter(user__account_status=User.AccountStatus.ACTIVE),
        empty_label="Select your OJT coordinator",
    )
    contact_number = forms.CharField(max_length=20, required=False)

    field_order = [
        "first_name", "last_name", "email", "student_number", "program",
        "year_level", "coordinator", "contact_number", "password1", "password2",
    ]

    def clean_student_number(self):
        number = self.cleaned_data["student_number"].strip()
        if Student.objects.filter(student_number=number).exists():  # BR-07
            raise forms.ValidationError("This student number is already registered.")
        return number

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.STUDENT
        user.save()
        student = Student(
            user=user,
            coordinator=self.cleaned_data["coordinator"],
            student_number=self.cleaned_data["student_number"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            program=self.cleaned_data["program"],
            year_level=self.cleaned_data["year_level"],
            contact_number=self.cleaned_data.get("contact_number") or None,
        )
        student.full_clean(exclude=["user"])
        student.save()
        return user


class CompanyRegistrationForm(BaseRegistrationForm):
    company_name = forms.CharField(max_length=150)
    industry = forms.CharField(max_length=80, required=False)
    address = forms.CharField(max_length=255)
    city = forms.CharField(max_length=100)
    contact_person = forms.CharField(max_length=100)
    contact_number = forms.CharField(max_length=20)
    website_url = forms.URLField(max_length=255, required=False)

    field_order = [
        "company_name", "industry", "email", "address", "city",
        "contact_person", "contact_number", "website_url", "password1", "password2",
    ]

    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.role = User.Role.COMPANY
        user.save()
        company = Company(
            user=user,
            company_name=self.cleaned_data["company_name"],
            industry=self.cleaned_data.get("industry") or None,
            address=self.cleaned_data["address"],
            city=self.cleaned_data["city"],
            contact_person=self.cleaned_data["contact_person"],
            contact_number=self.cleaned_data["contact_number"],
            website_url=self.cleaned_data.get("website_url") or None,
            # verification_status defaults to "pending" (BR-10)
        )
        company.full_clean(exclude=["user"])
        company.save()
        return user

    def clean_contact_number(self):
        from .models import phone_validator

        value = self.cleaned_data["contact_number"].strip()
        phone_validator(value)
        return value


# --------------------------------------------------------------------------
# Login (BR-03 lockout, BR-04 deactivated accounts)
# --------------------------------------------------------------------------
class LoginForm(StyledFormMixin, forms.Form):
    email = forms.EmailField(max_length=100)
    password = forms.CharField(widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned = super().clean()
        email = (cleaned.get("email") or "").strip().lower()
        password = cleaned.get("password")
        if not email or not password:
            return cleaned

        account = User.objects.filter(email__iexact=email).first()

        if account and account.is_locked():
            raise forms.ValidationError(
                f"This account is locked because of too many failed login attempts. "
                f"Try again in {account.minutes_until_unlock()} minute(s)."
            )

        user = authenticate(self.request, username=email, password=password)

        if user is None:
            if account and not account.is_active and account.check_password(password):
                raise forms.ValidationError("This account has been deactivated. Please contact your coordinator.")
            if account and account.is_active:
                account.register_failed_login()
                if account.is_locked():
                    raise forms.ValidationError(
                        "Too many failed login attempts. Your account is locked for 15 minutes."
                    )
            raise forms.ValidationError("Invalid email or password.")

        user.reset_failed_logins()
        self.user_cache = user
        return cleaned

    def get_user(self):
        return self.user_cache


# --------------------------------------------------------------------------
# Profile editing
# --------------------------------------------------------------------------
class AccountEmailForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = User
        fields = ("email",)

    def clean_email(self):
        return clean_unique_email(self.cleaned_data["email"], exclude_pk=self.instance.pk)


class StudentProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Student
        # student_number and coordinator are fixed after registration
        fields = ("first_name", "last_name", "program", "year_level", "contact_number", "resume_url", "portfolio_url")
        labels = {"resume_url": "Resume link (e.g. Google Drive)", "portfolio_url": "Portfolio link"}


class CompanyProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = Company
        fields = (
            "company_name", "industry", "address", "city", "description",
            "website_url", "contact_person", "contact_number",
        )
        labels = {"description": "Company profile (shown to students)"}
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class CoordinatorProfileForm(StyledFormMixin, forms.ModelForm):
    class Meta:
        model = SchoolCoordinator
        fields = ("first_name", "last_name", "department", "contact_number")


PROFILE_FORMS = {
    User.Role.STUDENT: StudentProfileForm,
    User.Role.COMPANY: CompanyProfileForm,
    User.Role.COORDINATOR: CoordinatorProfileForm,
}
