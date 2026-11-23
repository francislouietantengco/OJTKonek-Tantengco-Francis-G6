from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import Company
from accounts.tests import make_company, make_coordinator, make_student

from .models import Field, OjtPosting


def make_posting(company, **overrides):
    data = dict(
        company=company,
        field=Field.objects.get(field_name="Web Development"),
        title="Junior Web Developer Intern",
        description="Build Django features.",
        location="Cebu City",
        duration_weeks=12,
        slots=2,
        application_deadline=timezone.localdate() + timedelta(days=30),
        status=OjtPosting.Status.OPEN,
    )
    data.update(overrides)
    return OjtPosting.objects.create(**data)


def posting_form_data(**overrides):
    data = {
        "title": "QA Intern",
        "field": Field.objects.get(field_name="QA/Testing").pk,
        "location": "Mandaue City",
        "duration_weeks": "10",
        "slots": "3",
        "application_deadline": (timezone.localdate() + timedelta(days=14)).isoformat(),
        "description": "Help test our web apps.",
        "requirements": "Attention to detail",
    }
    data.update(overrides)
    return data


class PostingSetupMixin:
    def setUp(self):
        self.coordinator = make_coordinator()
        self.company_user = make_company()
        self.company = self.company_user.company_profile
        self.company.verify(self.coordinator)
        self.student = make_student(self.coordinator)


class CompanyPostingTests(PostingSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.company_user)

    def test_create_and_publish(self):
        resp = self.client.post(reverse("postings:create"), {**posting_form_data(), "publish": "1"}, follow=True)
        self.assertContains(resp, "is now open to students")
        posting = OjtPosting.objects.get(title="QA Intern")
        self.assertEqual(posting.company, self.company)
        self.assertEqual(posting.status, OjtPosting.Status.OPEN)
        self.assertIsNotNone(posting.published_at)

    def test_create_draft(self):
        self.client.post(reverse("postings:create"), {**posting_form_data(), "save_draft": "1"})
        self.assertEqual(OjtPosting.objects.get(title="QA Intern").status, OjtPosting.Status.DRAFT)

    def test_required_fields(self):
        resp = self.client.post(reverse("postings:create"), posting_form_data(title="", location=""))
        self.assertContains(resp, "This field is required", count=2)
        self.assertFalse(OjtPosting.objects.exists())

    def test_duration_and_slots_limits(self):
        resp = self.client.post(reverse("postings:create"), posting_form_data(duration_weeks="30", slots="0"))
        self.assertContains(resp, "less than or equal to 24")
        self.assertContains(resp, "greater than or equal to 1")

    def test_deadline_cannot_be_in_past(self):
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        resp = self.client.post(reverse("postings:create"), posting_form_data(application_deadline=past))
        self.assertContains(resp, "cannot be earlier than the posting date")

    def test_unverified_company_cannot_publish(self):
        self.company.verification_status = Company.VerificationStatus.PENDING
        self.company.save()
        resp = self.client.post(reverse("postings:create"), {**posting_form_data(), "publish": "1"}, follow=True)
        self.assertContains(resp, "Saved as a draft")
        self.assertEqual(OjtPosting.objects.get().status, OjtPosting.Status.DRAFT)

    def test_edit_posting(self):
        posting = make_posting(self.company)
        resp = self.client.post(reverse("postings:edit", args=[posting.pk]), posting_form_data(title="Updated title"), follow=True)
        self.assertContains(resp, "Your posting was updated")
        posting.refresh_from_db()
        self.assertEqual(posting.title, "Updated title")

    def test_close_is_soft_delete(self):
        posting = make_posting(self.company)
        self.client.post(reverse("postings:close", args=[posting.pk]))
        posting.refresh_from_db()
        self.assertEqual(posting.status, OjtPosting.Status.CLOSED)

    def test_cannot_touch_other_companys_posting(self):
        other = make_company(email="hr@other.com")
        other.company_profile.verify(self.coordinator)
        posting = make_posting(other.company_profile)
        self.assertEqual(self.client.get(reverse("postings:manage_detail", args=[posting.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("postings:close", args=[posting.pk])).status_code, 404)
        posting.refresh_from_db()
        self.assertEqual(posting.status, OjtPosting.Status.OPEN)

    def test_rejecting_company_closes_open_postings(self):
        posting = make_posting(self.company)
        self.company.reject(self.coordinator, "Permit expired, please renew.")
        posting.refresh_from_db()
        self.assertEqual(posting.status, OjtPosting.Status.CLOSED)


class StudentBrowseTests(PostingSetupMixin, TestCase):
    def setUp(self):
        super().setUp()
        self.client.force_login(self.student)

    def test_only_open_verified_postings_visible(self):
        make_posting(self.company, title="Visible posting")
        make_posting(self.company, title="Draft posting", status=OjtPosting.Status.DRAFT)
        pending = make_company(email="hr@pending.com").company_profile
        make_posting(pending, title="Pending company posting")
        resp = self.client.get(reverse("postings:browse"))
        self.assertContains(resp, "Visible posting")
        self.assertNotContains(resp, "Draft posting")
        self.assertNotContains(resp, "Pending company posting")

    def test_filters(self):
        make_posting(self.company, title="Web job", location="Cebu City", duration_weeks=8)
        make_posting(
            self.company, title="Network job", location="Manila", duration_weeks=20,
            field=Field.objects.get(field_name="Networking"),
        )
        resp = self.client.get(reverse("postings:browse"), {"location": "manila"})
        self.assertContains(resp, "Network job")
        self.assertNotContains(resp, "Web job")
        resp = self.client.get(reverse("postings:browse"), {"duration": "4-8"})
        self.assertContains(resp, "Web job")
        self.assertNotContains(resp, "Network job")
        resp = self.client.get(reverse("postings:browse"), {"q": "network"})
        self.assertContains(resp, "Network job")

    def test_expired_postings_close_automatically(self):
        posting = make_posting(self.company)
        OjtPosting.objects.filter(pk=posting.pk).update(application_deadline=timezone.localdate() - timedelta(days=1))
        self.client.get(reverse("postings:browse"))
        posting.refresh_from_db()
        self.assertEqual(posting.status, OjtPosting.Status.CLOSED)

    def test_student_cannot_manage_postings(self):
        posting = make_posting(self.company)
        self.assertEqual(self.client.get(reverse("postings:my_postings")).status_code, 302)
        self.assertEqual(self.client.get(reverse("postings:edit", args=[posting.pk])).status_code, 302)

    def test_detail_hidden_for_draft(self):
        draft = make_posting(self.company, status=OjtPosting.Status.DRAFT)
        self.assertEqual(self.client.get(reverse("postings:detail", args=[draft.pk])).status_code, 404)
