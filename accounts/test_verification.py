from django.test import TestCase
from django.urls import reverse

from .models import Company
from .tests import make_company, make_coordinator, make_student


class CompanyVerificationTests(TestCase):
    def setUp(self):
        self.coordinator = make_coordinator()
        self.company_user = make_company()
        self.company = self.company_user.company_profile
        self.client.force_login(self.coordinator.user)

    def test_coordinator_sees_pending_companies(self):
        resp = self.client.get(reverse("accounts:company_list"))
        self.assertContains(resp, "Acme Tech")

    def test_verify_records_coordinator_and_date(self):
        resp = self.client.post(reverse("accounts:company_verify", args=[self.company.pk]), follow=True)
        self.assertContains(resp, "is now verified")
        self.company.refresh_from_db()
        self.assertEqual(self.company.verification_status, Company.VerificationStatus.VERIFIED)
        self.assertEqual(self.company.verified_by, self.coordinator)
        self.assertIsNotNone(self.company.verified_at)

    def test_reject_requires_reason(self):
        resp = self.client.post(reverse("accounts:company_reject", args=[self.company.pk]), {"rejection_reason": ""})
        self.assertContains(resp, "Please enter a reason")
        self.company.refresh_from_db()
        self.assertEqual(self.company.verification_status, Company.VerificationStatus.PENDING)

    def test_reject_with_reason(self):
        self.client.post(
            reverse("accounts:company_reject", args=[self.company.pk]),
            {"rejection_reason": "Business permit could not be confirmed."},
        )
        self.company.refresh_from_db()
        self.assertEqual(self.company.verification_status, Company.VerificationStatus.REJECTED)
        self.assertIn("permit", self.company.rejection_reason)

    def test_rejected_company_resubmits_by_editing_profile(self):
        self.company.reject(self.coordinator, "Missing business permit details.")
        self.client.force_login(self.company_user)
        self.client.post(
            reverse("accounts:profile_edit"),
            {
                "account-email": "hr@acme.com",
                "profile-company_name": "Acme Tech", "profile-industry": "", "profile-address": "1 Road",
                "profile-city": "Cebu City", "profile-description": "Permit no. 123", "profile-website_url": "",
                "profile-contact_person": "Ana Reyes", "profile-contact_number": "09171234567",
            },
        )
        self.company.refresh_from_db()
        self.assertEqual(self.company.verification_status, Company.VerificationStatus.PENDING)

    def test_other_roles_cannot_verify(self):
        for user in [self.company_user, make_student(self.coordinator)]:
            self.client.force_login(user)
            self.client.post(reverse("accounts:company_verify", args=[self.company.pk]))
            self.assertEqual(self.client.get(reverse("accounts:company_list")).status_code, 302)
        self.company.refresh_from_db()
        self.assertEqual(self.company.verification_status, Company.VerificationStatus.PENDING)
