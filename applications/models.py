"""
Application Submission (F-07) and Applicant Tracking (F-08), following the SDD:
  applications
"""
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.utils import timezone

from accounts.models import Student
from postings.models import OjtPosting

MAX_ACTIVE_APPLICATIONS = 5  # BR-21


class Application(models.Model):
    """Table: applications — a student's application to one posting."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UNDER_REVIEW = "under_review", "Under Review"
        ACCEPTED = "accepted", "Accepted"
        REJECTED = "rejected", "Rejected"
        WITHDRAWN = "withdrawn", "Withdrawn"

    ACTIVE = (Status.PENDING, Status.UNDER_REVIEW)

    # BR-22 / BR-23: allowed status changes. Accepted, Rejected and Withdrawn are final.
    TRANSITIONS = {
        Status.PENDING: {Status.UNDER_REVIEW, Status.ACCEPTED, Status.REJECTED, Status.WITHDRAWN},
        Status.UNDER_REVIEW: {Status.ACCEPTED, Status.REJECTED, Status.WITHDRAWN},
        Status.ACCEPTED: set(),
        Status.REJECTED: set(),
        Status.WITHDRAWN: set(),
    }

    application_id = models.AutoField(primary_key=True)
    student = models.ForeignKey(
        Student, on_delete=models.PROTECT, related_name="applications", db_column="student_id"
    )
    posting = models.ForeignKey(
        OjtPosting, on_delete=models.PROTECT, related_name="applications", db_column="posting_id"
    )
    cover_letter = models.TextField(blank=True, null=True)
    resume_url_snapshot = models.URLField(max_length=255)  # BR-09
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    submitted_at = models.DateTimeField(default=timezone.now)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewer_remarks = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "applications"
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(fields=["student", "posting"], name="applications_one_per_posting"),  # BR-19
            models.CheckConstraint(
                condition=~models.Q(status="rejected") | models.Q(reviewer_remarks__isnull=False),
                name="applications_rejection_needs_remarks",
            ),  # BR-25
            models.CheckConstraint(
                condition=models.Q(status__in=["pending", "under_review", "accepted", "rejected", "withdrawn"]),
                name="applications_status_valid",
            ),
        ]

    def __str__(self):
        return f"{self.student} → {self.posting.title}"

    # --- Helpers ---------------------------------------------------------------
    @property
    def is_active(self):
        return self.status in self.ACTIVE

    @property
    def can_withdraw(self):
        return self.status in self.ACTIVE  # BR-23

    @property
    def can_edit(self):
        return self.status == self.Status.PENDING

    def _change_status(self, new_status):
        if new_status not in self.TRANSITIONS[self.status]:
            raise ValidationError(
                f"An application that is {self.get_status_display()} cannot be changed to "
                f"{self.Status(new_status).label}."
            )
        self.status = new_status

    # --- Student actions -------------------------------------------------------
    @classmethod
    def check_can_apply(cls, student, posting):
        """Raise ValidationError with a clear message if the student may not apply (BR-09, 19, 20, 21)."""
        if not student.resume_url:
            raise ValidationError("Add a resume link to your profile before applying.")
        if posting.status != OjtPosting.Status.OPEN or posting.deadline_passed or not posting.company.is_verified:
            raise ValidationError("This posting is no longer accepting applications.")
        if cls.objects.filter(student=student, posting=posting).exists():
            raise ValidationError("You have already applied to this posting.")
        active = cls.objects.filter(student=student, status__in=cls.ACTIVE).count()
        if active >= MAX_ACTIVE_APPLICATIONS:
            raise ValidationError(
                f"You already have {MAX_ACTIVE_APPLICATIONS} active applications. "
                "Withdraw one or wait for a decision before applying again."
            )

    def withdraw(self):
        self._change_status(self.Status.WITHDRAWN)
        self.save(update_fields=["status"])

    # --- Company actions -------------------------------------------------------
    def mark_under_review(self):
        self._change_status(self.Status.UNDER_REVIEW)
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewed_at"])

    def reject(self, remarks):
        if not remarks or not remarks.strip():
            raise ValidationError("Remarks are required when rejecting an application.")  # BR-25
        self._change_status(self.Status.REJECTED)
        self.reviewer_remarks = remarks.strip()
        self.reviewed_at = timezone.now()
        self.save(update_fields=["status", "reviewer_remarks", "reviewed_at"])

    def accept(self, remarks=""):
        with transaction.atomic():
            posting = OjtPosting.objects.select_for_update().get(pk=self.posting_id)
            accepted = posting.applications.filter(status=self.Status.ACCEPTED).count()
            if accepted >= posting.slots:  # BR-26
                raise ValidationError("All slots for this posting are already filled.")
            self._change_status(self.Status.ACCEPTED)
            self.reviewer_remarks = remarks.strip() or None
            self.reviewed_at = timezone.now()
            self.save(update_fields=["status", "reviewer_remarks", "reviewed_at"])
            # BR-18: close the posting automatically once accepted applicants equal its slots.
            if accepted + 1 >= posting.slots and posting.status == OjtPosting.Status.OPEN:
                posting.close()
                return True
        return False
