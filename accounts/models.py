"""
Account models for OJT Konek, following the SDD data dictionary:
  users, school_coordinators, students, companies
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.validators import MaxValueValidator, MinValueValidator, RegexValidator
from django.db import models, transaction
from django.utils import timezone

phone_validator = RegexValidator(r"^\+?\d{7,15}$", "Enter a valid contact number (7–15 digits, optional +).")


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra_fields)
        user.set_password(password)  # hashes the password (BR-02)
        user.save(using=self._db)
        return user

    @transaction.atomic
    def create_superuser(self, email, password=None, **extra_fields):
        """
        The superuser is the system administrator. It gets the Coordinator role and a
        coordinator profile so it can use the site and manage accounts in /admin.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.COORDINATOR)
        user = self.create_user(email, password, **extra_fields)
        SchoolCoordinator.objects.create(
            user=user, first_name="System", last_name="Administrator", department="College of Computer Studies"
        )
        return user


class User(AbstractBaseUser, PermissionsMixin):
    """Table: users — the login account of every Student, Company and School Coordinator."""

    class Role(models.TextChoices):
        STUDENT = "student", "Student"
        COMPANY = "company", "Company"
        COORDINATOR = "coordinator", "School Coordinator"

    class AccountStatus(models.TextChoices):
        ACTIVE = "active", "Active"
        DEACTIVATED = "deactivated", "Deactivated"

    user_id = models.AutoField(primary_key=True)
    email = models.EmailField(max_length=100, unique=True)  # BR-01
    password = models.CharField(max_length=255, db_column="password_hash")  # BR-02: hash only
    role = models.CharField(max_length=20, choices=Role.choices)  # BR-01
    account_status = models.CharField(
        max_length=20, choices=AccountStatus.choices, default=AccountStatus.ACTIVE
    )  # BR-04, BR-06
    failed_login_count = models.PositiveSmallIntegerField(default=0)  # BR-03
    locked_until = models.DateTimeField(null=True, blank=True)  # BR-03
    created_at = models.DateTimeField(default=timezone.now)
    last_login = models.DateTimeField(null=True, blank=True, db_column="last_login_at")
    is_staff = models.BooleanField(default=False, help_text="Can log in to the Django admin site.")

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(failed_login_count__gte=0, failed_login_count__lte=5),
                name="users_failed_login_count_0_to_5",
            ),
            models.CheckConstraint(
                condition=models.Q(role__in=["student", "company", "coordinator"]), name="users_role_valid"
            ),
            models.CheckConstraint(
                condition=models.Q(account_status__in=["active", "deactivated"]), name="users_status_valid"
            ),
        ]

    def __str__(self):
        return self.email

    # BR-04: Django's auth backend refuses users whose is_active is False.
    @property
    def is_active(self):
        return self.account_status == self.AccountStatus.ACTIVE

    # --- BR-03 lockout helpers --------------------------------------------
    def is_locked(self):
        return self.locked_until is not None and self.locked_until > timezone.now()

    def minutes_until_unlock(self):
        if not self.is_locked():
            return 0
        return max(1, int((self.locked_until - timezone.now()).total_seconds() // 60) + 1)

    def register_failed_login(self):
        """Count a failed attempt; lock the account on the 5th consecutive failure."""
        self.failed_login_count += 1
        if self.failed_login_count >= settings.MAX_FAILED_LOGINS:
            self.locked_until = timezone.now() + timedelta(minutes=settings.LOCKOUT_MINUTES)
            self.failed_login_count = 0  # start fresh after the lockout ends
        self.save(update_fields=["failed_login_count", "locked_until"])

    def reset_failed_logins(self):
        if self.failed_login_count or self.locked_until:
            self.failed_login_count = 0
            self.locked_until = None
            self.save(update_fields=["failed_login_count", "locked_until"])

    # --- Role helpers ------------------------------------------------------
    @property
    def profile(self):
        """The role-specific profile row (students / companies / school_coordinators)."""
        attr = {
            self.Role.STUDENT: "student_profile",
            self.Role.COMPANY: "company_profile",
            self.Role.COORDINATOR: "coordinator_profile",
        }.get(self.role)
        return getattr(self, attr, None) if attr else None

    @property
    def display_name(self):
        p = self.profile
        if p is None:
            return self.email
        if self.role == self.Role.COMPANY:
            return p.company_name
        return f"{p.first_name} {p.last_name}"


class SchoolCoordinator(models.Model):
    """Table: school_coordinators."""

    coordinator_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(
        User, on_delete=models.PROTECT, related_name="coordinator_profile", db_column="user_id"
    )
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    department = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=20, blank=True, null=True, validators=[phone_validator])

    class Meta:
        db_table = "school_coordinators"
        ordering = ["last_name", "first_name"]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.department})"


class Student(models.Model):
    """Table: students."""

    class Program(models.TextChoices):
        BSIT = "BSIT", "BSIT"
        BSCS = "BSCS", "BSCS"

    student_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="student_profile", db_column="user_id")
    coordinator = models.ForeignKey(
        SchoolCoordinator, on_delete=models.PROTECT, related_name="students", db_column="coordinator_id"
    )  # BR-08
    student_number = models.CharField(
        max_length=15,
        unique=True,
        validators=[RegexValidator(r"^\d{2}-\d{4}-\d{3}$", "Use the format 23-7573-680.")],
    )  # BR-07
    first_name = models.CharField(max_length=50)
    last_name = models.CharField(max_length=50)
    program = models.CharField(max_length=4, choices=Program.choices)  # BR-07
    year_level = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(4)])
    contact_number = models.CharField(max_length=20, blank=True, null=True, validators=[phone_validator])
    resume_url = models.URLField(max_length=255, blank=True, null=True)  # BR-09
    portfolio_url = models.URLField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "students"
        ordering = ["last_name", "first_name"]
        constraints = [
            models.CheckConstraint(condition=models.Q(program__in=["BSIT", "BSCS"]), name="students_program_valid"),
            models.CheckConstraint(
                condition=models.Q(year_level__gte=1, year_level__lte=4), name="students_year_level_1_to_4"
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.student_number})"


class Company(models.Model):
    """Table: companies."""

    class VerificationStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        VERIFIED = "verified", "Verified"
        REJECTED = "rejected", "Rejected"

    company_id = models.AutoField(primary_key=True)
    user = models.OneToOneField(User, on_delete=models.PROTECT, related_name="company_profile", db_column="user_id")
    company_name = models.CharField(max_length=150)
    industry = models.CharField(max_length=80, blank=True, null=True)
    address = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)
    website_url = models.URLField(max_length=255, blank=True, null=True)
    contact_person = models.CharField(max_length=100)
    contact_number = models.CharField(max_length=20, validators=[phone_validator])
    verification_status = models.CharField(
        max_length=10, choices=VerificationStatus.choices, default=VerificationStatus.PENDING
    )  # BR-10
    verified_by = models.ForeignKey(
        SchoolCoordinator,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="verified_companies",
        db_column="verified_by",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "companies"
        verbose_name_plural = "companies"
        ordering = ["company_name"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(verification_status__in=["pending", "verified", "rejected"]),
                name="companies_verification_status_valid",
            ),
            models.CheckConstraint(
                condition=~models.Q(verification_status="rejected") | models.Q(rejection_reason__isnull=False),
                name="companies_rejection_needs_reason",
            ),
        ]

    def __str__(self):
        return self.company_name

    @property
    def is_verified(self):
        return self.verification_status == self.VerificationStatus.VERIFIED

    # --- F-04 Company Verification (BR-10) -----------------------------------
    def verify(self, coordinator):
        self.verification_status = self.VerificationStatus.VERIFIED
        self.verified_by = coordinator
        self.verified_at = timezone.now()
        self.rejection_reason = None
        self.save(update_fields=["verification_status", "verified_by", "verified_at", "rejection_reason"])

    def reject(self, coordinator, reason):
        self.verification_status = self.VerificationStatus.REJECTED
        self.verified_by = coordinator
        self.verified_at = timezone.now()
        self.rejection_reason = reason
        self.save(update_fields=["verification_status", "verified_by", "verified_at", "rejection_reason"])

    def resubmit(self):
        """A rejected company that updates its profile goes back to Pending for review."""
        self.verification_status = self.VerificationStatus.PENDING
        self.save(update_fields=["verification_status"])
