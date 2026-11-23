from django.test import TestCase
from django.urls import reverse

from accounts.tests import make_company, make_coordinator, make_student
from postings.models import Field, OjtPosting
from postings.tests import make_posting, posting_form_data

from .models import Application

RESUME = "https://drive.google.com/resume"


class ApplicationSetupMixin:
    def setUp(self):
        self.coordinator = make_coordinator()
        self.company_user = make_company()
        self.company = self.company_user.company_profile
        self.company.verify(self.coordinator)
        self.posting = make_posting(self.company, slots=1)
        self.student_user = make_student(self.coordinator)
        self.student = self.student_user.student_profile
        self.student.resume_url = RESUME
        self.student.save()

    def apply(self, posting=None, user=None, cover="I would love to join."):
        self.client.force_login(user or self.student_user)
        return self.client.post(
            reverse("applications:apply", args=[(posting or self.posting).pk]), {"cover_letter": cover}, follow=True
        )


class StudentApplicationTests(ApplicationSetupMixin, TestCase):
    def test_apply_creates_pending_application_with_resume_snapshot(self):
        resp = self.apply()
        self.assertContains(resp, "was submitted")
        app = Application.objects.get()
        self.assertEqual(app.status, Application.Status.PENDING)
        self.assertEqual(app.student, self.student)
        self.assertEqual(app.resume_url_snapshot, RESUME)

    def test_resume_required(self):
        self.student.resume_url = None
        self.student.save()
        resp = self.apply()
        self.assertContains(resp, "Add a resume link")
        self.assertFalse(Application.objects.exists())

    def test_cannot_apply_twice(self):
        self.apply()
        resp = self.apply()
        self.assertContains(resp, "already applied")
        self.assertEqual(Application.objects.count(), 1)

    def test_cannot_apply_to_closed_posting(self):
        self.posting.close()
        resp = self.apply()
        self.assertContains(resp, "no longer accepting")
        self.assertFalse(Application.objects.exists())

    def test_max_five_active_applications(self):
        for i in range(5):
            self.apply(make_posting(self.company, title=f"Posting {i}"))
        resp = self.apply()
        self.assertContains(resp, "already have 5 active applications")
        self.assertEqual(Application.objects.count(), 5)

    def test_edit_cover_letter_while_pending(self):
        self.apply()
        app = Application.objects.get()
        resp = self.client.post(reverse("applications:edit", args=[app.pk]), {"cover_letter": "New letter"}, follow=True)
        self.assertContains(resp, "cover letter was updated")
        app.refresh_from_db()
        self.assertEqual(app.cover_letter, "New letter")

    def test_withdraw(self):
        self.apply()
        app = Application.objects.get()
        self.client.post(reverse("applications:withdraw", args=[app.pk]))
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.WITHDRAWN)

    def test_cannot_withdraw_after_decision(self):
        self.apply()
        app = Application.objects.get()
        app.reject("Not a fit right now.")
        resp = self.client.post(reverse("applications:withdraw", args=[app.pk]), follow=True)
        self.assertContains(resp, "cannot be changed")
        app.refresh_from_db()
        self.assertEqual(app.status, Application.Status.REJECTED)

    def test_students_only_see_own_applications(self):
        self.apply()
        app = Application.objects.get()
        other = make_student(self.coordinator, email="other@school.edu", number="23-0000-001")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("applications:detail", args=[app.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("applications:withdraw", args=[app.pk])).status_code, 404)


class CompanyReviewTests(ApplicationSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.apply()
        self.app = Application.objects.get()
        self.client.force_login(self.company_user)

    def decide(self, action, remarks=""):
        return self.client.post(
            reverse("applications:decide", args=[self.app.pk]), {"action": action, "remarks": remarks}, follow=True
        )

    def test_company_sees_applicants(self):
        resp = self.client.get(reverse("applications:posting_applicants", args=[self.posting.pk]))
        self.assertContains(resp, "Dela Cruz")

    def test_mark_under_review(self):
        self.decide("review")
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.UNDER_REVIEW)

    def test_reject_requires_remarks(self):
        resp = self.decide("reject")
        self.assertContains(resp, "Remarks are required")
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.PENDING)

    def test_reject_with_remarks(self):
        self.decide("reject", "We need someone with networking skills.")
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.REJECTED)
        self.assertIsNotNone(self.app.reviewed_at)

    def test_accept_fills_slot_and_closes_posting(self):
        resp = self.decide("accept", "Welcome aboard!")
        self.assertContains(resp, "posting was closed automatically")
        self.app.refresh_from_db()
        self.posting.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.ACCEPTED)
        self.assertEqual(self.posting.status, OjtPosting.Status.CLOSED)

    def test_cannot_accept_beyond_slots(self):
        self.posting.slots = 2
        self.posting.save()
        second_user = make_student(self.coordinator, email="b@school.edu", number="23-0000-002")
        second = second_user.student_profile
        second.resume_url = RESUME
        second.save()
        third_user = make_student(self.coordinator, email="c@school.edu", number="23-0000-003")
        third = third_user.student_profile
        third.resume_url = RESUME
        third.save()
        a2 = Application.objects.create(student=second, posting=self.posting, resume_url_snapshot=RESUME)
        a3 = Application.objects.create(student=third, posting=self.posting, resume_url_snapshot=RESUME)
        self.app.accept()
        a2.accept()
        with self.assertRaises(Exception):
            a3.accept()
        a3.refresh_from_db()
        self.assertEqual(a3.status, Application.Status.PENDING)

    def test_final_status_cannot_change(self):
        self.decide("accept")
        resp = self.decide("reject", "Changed our mind about this.")
        self.assertContains(resp, "cannot be changed")
        self.app.refresh_from_db()
        self.assertEqual(self.app.status, Application.Status.ACCEPTED)

    def test_other_company_cannot_review(self):
        other = make_company(email="hr@other.com")
        self.client.force_login(other)
        self.assertEqual(self.client.get(reverse("applications:applicant_detail", args=[self.app.pk])).status_code, 404)
        self.assertEqual(self.decide("accept").status_code, 404)

    def test_field_and_duration_locked_after_application(self):
        data = posting_form_data(title="Same title", duration_weeks="20",
                                 field=Field.objects.get(field_name="Networking").pk)
        self.client.post(reverse("postings:edit", args=[self.posting.pk]), data)
        self.posting.refresh_from_db()
        self.assertEqual(self.posting.title, "Same title")
        self.assertEqual(self.posting.duration_weeks, 12)
        self.assertEqual(self.posting.field.field_name, "Web Development")


class CoordinatorOverviewTests(ApplicationSetupMixin, TestCase):
    def test_coordinator_sees_assigned_students_applications(self):
        self.apply()
        self.client.force_login(self.coordinator.user)
        resp = self.client.get(reverse("applications:student_applications"))
        self.assertContains(resp, self.posting.title)

    def test_coordinator_does_not_see_other_coordinators_students(self):
        other = make_coordinator(email="other@school.edu")
        self.apply()
        self.client.force_login(other.user)
        resp = self.client.get(reverse("applications:student_applications"))
        self.assertNotContains(resp, self.posting.title)
