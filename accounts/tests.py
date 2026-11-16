from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import Company, SchoolCoordinator, Student, User

PASSWORD = "Konek2026pass"


def make_coordinator(email="coord@school.edu"):
    user = User.objects.create_user(email=email, password=PASSWORD, role=User.Role.COORDINATOR)
    return SchoolCoordinator.objects.create(user=user, first_name="Maria", last_name="Santos", department="CCS")


def make_student(coordinator, email="stud@school.edu", number="23-7573-680"):
    user = User.objects.create_user(email=email, password=PASSWORD, role=User.Role.STUDENT)
    Student.objects.create(
        user=user, coordinator=coordinator, student_number=number,
        first_name="Juan", last_name="Dela Cruz", program="BSIT", year_level=3,
    )
    return user


def make_company(email="hr@acme.com"):
    user = User.objects.create_user(email=email, password=PASSWORD, role=User.Role.COMPANY)
    Company.objects.create(
        user=user, company_name="Acme Tech", address="1 Road", city="Cebu City",
        contact_person="Ana Reyes", contact_number="09171234567",
    )
    return user


class RegistrationTests(TestCase):
    def setUp(self):
        self.coordinator = make_coordinator()

    def student_data(self, **overrides):
        data = {
            "first_name": "Juan", "last_name": "Dela Cruz", "email": "juan@school.edu",
            "student_number": "23-1111-222", "program": "BSCS", "year_level": "2",
            "coordinator": self.coordinator.pk, "contact_number": "",
            "password1": PASSWORD, "password2": PASSWORD,
        }
        data.update(overrides)
        return data

    def test_student_registration_hashes_password_and_creates_profile(self):
        resp = self.client.post(reverse("accounts:register_student"), self.student_data(), follow=True)
        self.assertContains(resp, "Your student account was created")
        user = User.objects.get(email="juan@school.edu")
        self.assertEqual(user.role, User.Role.STUDENT)
        self.assertNotEqual(user.password, PASSWORD)
        self.assertTrue(user.password.startswith("pbkdf2_"))
        self.assertEqual(user.student_profile.coordinator, self.coordinator)

    def test_password_mismatch(self):
        resp = self.client.post(reverse("accounts:register_student"), self.student_data(password2="Other12345"))
        self.assertContains(resp, "didn’t match")
        self.assertFalse(User.objects.filter(email="juan@school.edu").exists())

    def test_password_needs_letter_and_number(self):
        resp = self.client.post(
            reverse("accounts:register_student"),
            self.student_data(password1="abcdefghij", password2="abcdefghij"),
        )
        self.assertContains(resp, "at least one letter and one number")

    def test_duplicate_email_rejected(self):
        resp = self.client.post(reverse("accounts:register_student"), self.student_data(email="COORD@school.edu"))
        self.assertContains(resp, "An account with this email already exists")

    def test_invalid_email_and_required_fields(self):
        resp = self.client.post(reverse("accounts:register_student"), self.student_data(email="not-an-email", first_name=""))
        self.assertContains(resp, "Enter a valid email address")
        self.assertContains(resp, "This field is required")

    def test_duplicate_student_number_rejected(self):
        make_student(self.coordinator, number="23-1111-222")
        resp = self.client.post(reverse("accounts:register_student"), self.student_data())
        self.assertContains(resp, "student number is already registered")

    def test_company_registration_is_pending(self):
        data = {
            "company_name": "Acme", "industry": "Software", "email": "hr@acme.com", "address": "1 Road",
            "city": "Cebu City", "contact_person": "Ana", "contact_number": "09171234567",
            "website_url": "", "password1": PASSWORD, "password2": PASSWORD,
        }
        resp = self.client.post(reverse("accounts:register_company"), data, follow=True)
        self.assertContains(resp, "must verify it")
        company = Company.objects.get(company_name="Acme")
        self.assertEqual(company.verification_status, Company.VerificationStatus.PENDING)


class LoginTests(TestCase):
    def setUp(self):
        self.coordinator = make_coordinator()
        self.student = make_student(self.coordinator)
        self.url = reverse("accounts:login")

    def test_login_redirects_to_role_dashboard(self):
        resp = self.client.post(self.url, {"email": "stud@school.edu", "password": PASSWORD}, follow=True)
        self.assertRedirects(resp, reverse("accounts:student_dashboard"))

    def test_invalid_credentials_show_error(self):
        resp = self.client.post(self.url, {"email": "stud@school.edu", "password": "wrong123"})
        self.assertContains(resp, "Invalid email or password")

    def test_lockout_after_five_failures(self):
        for _ in range(5):
            self.client.post(self.url, {"email": "stud@school.edu", "password": "wrong123"})
        self.student.refresh_from_db()
        self.assertTrue(self.student.is_locked())
        resp = self.client.post(self.url, {"email": "stud@school.edu", "password": PASSWORD})
        self.assertContains(resp, "locked")
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_lock_expires(self):
        self.student.locked_until = timezone.now() - timedelta(minutes=1)
        self.student.save()
        resp = self.client.post(self.url, {"email": "stud@school.edu", "password": PASSWORD})
        self.assertEqual(resp.status_code, 302)

    def test_deactivated_account_cannot_log_in(self):
        self.student.account_status = User.AccountStatus.DEACTIVATED
        self.student.save()
        resp = self.client.post(self.url, {"email": "stud@school.edu", "password": PASSWORD})
        self.assertContains(resp, "deactivated")

    def test_logout_ends_session(self):
        self.client.force_login(self.student)
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
        resp = self.client.get(reverse("accounts:student_dashboard"))
        self.assertRedirects(resp, reverse("accounts:login") + "?next=" + reverse("accounts:student_dashboard"))


class AccessControlTests(TestCase):
    def setUp(self):
        self.coordinator = make_coordinator()
        self.student = make_student(self.coordinator)
        self.company = make_company()

    def test_logged_out_user_sent_to_login(self):
        for name in ["student_dashboard", "company_dashboard", "coordinator_dashboard", "profile", "profile_edit"]:
            resp = self.client.get(reverse(f"accounts:{name}"))
            self.assertEqual(resp.status_code, 302)
            self.assertTrue(resp.url.startswith(reverse("accounts:login")))

    def test_student_cannot_open_other_dashboards(self):
        self.client.force_login(self.student)
        for name in ["company_dashboard", "coordinator_dashboard"]:
            resp = self.client.get(reverse(f"accounts:{name}"))
            self.assertRedirects(resp, reverse("accounts:dashboard"), fetch_redirect_response=False)

    def test_company_cannot_open_coordinator_dashboard(self):
        self.client.force_login(self.company)
        resp = self.client.get(reverse("accounts:coordinator_dashboard"))
        self.assertEqual(resp.status_code, 302)

    def test_each_role_sees_own_dashboard(self):
        for user, name in [
            (self.student, "student_dashboard"),
            (self.company, "company_dashboard"),
            (self.coordinator.user, "coordinator_dashboard"),
        ]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse(f"accounts:{name}")).status_code, 200)


class ProfileTests(TestCase):
    def setUp(self):
        self.coordinator = make_coordinator()
        self.student = make_student(self.coordinator)

    def test_view_own_profile(self):
        self.client.force_login(self.student)
        resp = self.client.get(reverse("accounts:profile"))
        self.assertContains(resp, "23-7573-680")

    def test_update_profile(self):
        self.client.force_login(self.student)
        resp = self.client.post(
            reverse("accounts:profile_edit"),
            {
                "account-email": "new@school.edu",
                "profile-first_name": "Juanito", "profile-last_name": "Dela Cruz",
                "profile-program": "BSCS", "profile-year_level": 4,
                "profile-contact_number": "09181234567",
                "profile-resume_url": "https://drive.google.com/resume",
                "profile-portfolio_url": "",
            },
            follow=True,
        )
        self.assertContains(resp, "Your profile has been updated")
        self.student.refresh_from_db()
        self.assertEqual(self.student.email, "new@school.edu")
        self.assertEqual(self.student.student_profile.first_name, "Juanito")
        self.assertEqual(self.student.student_profile.resume_url, "https://drive.google.com/resume")
