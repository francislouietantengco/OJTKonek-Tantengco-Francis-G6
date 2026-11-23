"""
OJT Postings (F-05, F-06), following the SDD data dictionary:
  fields, ojt_postings
"""
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone

from accounts.models import Company


class Field(models.Model):
    """Table: fields — lookup table of OJT fields (e.g., Web Development, Networking)."""

    field_id = models.AutoField(primary_key=True)
    field_name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "fields"
        ordering = ["field_name"]

    def __str__(self):
        return self.field_name


class OjtPostingQuerySet(models.QuerySet):
    def visible_to_students(self):
        """BR-15: only Open postings of verified companies whose deadline has not passed."""
        return self.filter(
            status=OjtPosting.Status.OPEN,
            company__verification_status=Company.VerificationStatus.VERIFIED,
            application_deadline__gte=timezone.localdate(),
        )

    def expired(self):
        return self.filter(status=OjtPosting.Status.OPEN, application_deadline__lt=timezone.localdate())


class OjtPosting(models.Model):
    """Table: ojt_postings — OJT/internship openings published by companies."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    MIN_WEEKS, MAX_WEEKS = 4, 24

    posting_id = models.AutoField(primary_key=True)
    company = models.ForeignKey(
        Company, on_delete=models.PROTECT, related_name="postings", db_column="company_id"
    )  # BR-16 owner
    field = models.ForeignKey(Field, on_delete=models.PROTECT, related_name="postings", db_column="field_id")
    title = models.CharField(max_length=150)
    description = models.TextField()
    requirements = models.TextField(blank=True, null=True)
    location = models.CharField(max_length=100)
    duration_weeks = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_WEEKS), MaxValueValidator(MAX_WEEKS)]
    )  # BR-13
    slots = models.PositiveSmallIntegerField(validators=[MinValueValidator(1)])  # BR-13
    application_deadline = models.DateField()  # BR-14
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(null=True, blank=True)

    objects = OjtPostingQuerySet.as_manager()

    class Meta:
        db_table = "ojt_postings"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_weeks__gte=4, duration_weeks__lte=24),
                name="ojt_postings_duration_4_to_24",
            ),
            models.CheckConstraint(condition=models.Q(slots__gte=1), name="ojt_postings_slots_at_least_1"),
            models.CheckConstraint(
                condition=models.Q(status__in=["draft", "open", "closed"]), name="ojt_postings_status_valid"
            ),
        ]

    def __str__(self):
        return f"{self.title} — {self.company.company_name}"

    # --- Business rules ------------------------------------------------------
    @property
    def deadline_passed(self):
        return self.application_deadline < timezone.localdate()

    @property
    def accepted_count(self):
        return self.applications.filter(status="accepted").count()

    @property
    def is_open(self):
        return self.status == self.Status.OPEN

    def clean(self):
        # BR-11: a pending or rejected company may not have an Open posting.
        if self.status == self.Status.OPEN and not self.company.is_verified:
            raise ValidationError("Your company must be verified by a coordinator before you can publish postings.")
        # BR-14: the deadline may not be earlier than the creation date.
        created = timezone.localdate(self.created_at) if self.created_at else timezone.localdate()
        if self.application_deadline and self.application_deadline < created:
            raise ValidationError({"application_deadline": "The deadline cannot be earlier than the posting date."})

    def publish(self):
        """Draft/Closed -> Open. Raises ValidationError if a rule blocks it."""
        if not self.company.is_verified:
            raise ValidationError("Your company must be verified before you can publish postings.")
        if self.deadline_passed:
            raise ValidationError("The application deadline has passed. Move the deadline before publishing.")
        if self.pk and self.accepted_count >= self.slots:
            raise ValidationError("All slots are filled. Add more slots before reopening this posting.")
        self.status = self.Status.OPEN
        self.published_at = self.published_at or timezone.now()
        self.save(update_fields=["status", "published_at", "updated_at"])

    def close(self):
        self.status = self.Status.CLOSED
        self.save(update_fields=["status", "updated_at"])

    @classmethod
    def close_expired(cls):
        """BR-18: close Open postings whose deadline has passed. Returns how many were closed."""
        return cls.objects.expired().update(status=cls.Status.CLOSED, updated_at=timezone.now())
