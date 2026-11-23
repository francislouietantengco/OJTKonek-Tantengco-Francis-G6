from django.test import TestCase
from django.urls import reverse

from .models import User
from .tests import make_coordinator


class CoordinatorDropdownTests(TestCase):
    def test_superuser_profile_hidden_from_student_signup(self):
        User.objects.create_superuser(email="admin@ojtkonek.test", password="Admin2026pass")
        make_coordinator()
        resp = self.client.get(reverse("accounts:register_student"))
        self.assertContains(resp, "Maria Santos")
        self.assertNotContains(resp, "System Administrator")

    def test_warning_when_only_superuser_exists(self):
        User.objects.create_superuser(email="admin@ojtkonek.test", password="Admin2026pass")
        resp = self.client.get(reverse("accounts:register_student"))
        self.assertContains(resp, "Student registration opens once a school coordinator has been added")
