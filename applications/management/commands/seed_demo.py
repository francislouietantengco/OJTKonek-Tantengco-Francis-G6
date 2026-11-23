"""
Create one test account per role plus sample postings, for demos and the completion report.
Usage:  python manage.py seed_demo
Safe to run more than once (existing records are reused).
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.models import Company, SchoolCoordinator, Student, User
from applications.models import Application
from postings.models import Field, OjtPosting

PASSWORD = "OjtKonek2026"


def get_or_create_user(email, role):
    user, created = User.objects.get_or_create(email=email, defaults={"role": role})
    if created:
        user.set_password(PASSWORD)
        user.save()
    return user


class Command(BaseCommand):
    help = "Create demo accounts (coordinator, student, companies) and sample OJT postings."

    @transaction.atomic
    def handle(self, *args, **options):
        coord_user = get_or_create_user("coordinator@ojtkonek.test", User.Role.COORDINATOR)
        coordinator, _ = SchoolCoordinator.objects.get_or_create(
            user=coord_user,
            defaults=dict(first_name="Maria", last_name="Santos", department="College of Computer Studies",
                          contact_number="09171112222"),
        )

        student_user = get_or_create_user("student@ojtkonek.test", User.Role.STUDENT)
        student, _ = Student.objects.get_or_create(
            user=student_user,
            defaults=dict(coordinator=coordinator, student_number="23-0001-001", first_name="Juan",
                          last_name="Dela Cruz", program="BSIT", year_level=3, contact_number="09181234567",
                          resume_url="https://drive.google.com/file/d/demo-resume/view"),
        )

        company_user = get_or_create_user("company@ojtkonek.test", User.Role.COMPANY)
        company, _ = Company.objects.get_or_create(
            user=company_user,
            defaults=dict(company_name="Bytewave Solutions Inc.", industry="Software Development",
                          address="Unit 5, IT Park", city="Cebu City", contact_person="Ana Reyes",
                          contact_number="0322345678", website_url="https://example.com",
                          description="We build web and mobile apps for local businesses."),
        )
        if not company.is_verified:
            company.verify(coordinator)

        pending_user = get_or_create_user("pending.company@ojtkonek.test", User.Role.COMPANY)
        Company.objects.get_or_create(
            user=pending_user,
            defaults=dict(company_name="Northpoint Networks", industry="Telecommunications",
                          address="88 Osmeña Blvd", city="Cebu City", contact_person="Mark Lim",
                          contact_number="0329876543"),
        )

        deadline = timezone.localdate() + timedelta(days=30)
        samples = [
            ("Junior Web Developer Intern", "Web Development", "Cebu City", 12, 3,
             "Build features in Django and React with our product team.", "Python, HTML/CSS, Git"),
            ("QA Tester Intern", "QA/Testing", "Mandaue City", 8, 2,
             "Write test cases and test our web apps before release.", "Attention to detail"),
            ("Network Support Intern", "Networking", "Cebu City", 16, 1,
             "Help maintain office networks and troubleshoot issues.", "Basic networking (CCNA a plus)"),
        ]
        postings = []
        for title, field, location, weeks, slots, desc, req in samples:
            posting, _ = OjtPosting.objects.get_or_create(
                company=company, title=title,
                defaults=dict(field=Field.objects.get(field_name=field), location=location, duration_weeks=weeks,
                              slots=slots, application_deadline=deadline, description=desc, requirements=req),
            )
            if posting.status == OjtPosting.Status.DRAFT:
                posting.publish()
            postings.append(posting)

        Application.objects.get_or_create(
            student=student, posting=postings[0],
            defaults=dict(cover_letter="I am a 3rd-year BSIT student who enjoys building web apps.",
                          resume_url_snapshot=student.resume_url),
        )

        self.stdout.write(self.style.SUCCESS("Demo data ready. Test accounts (password for all: %s):" % PASSWORD))
        for email, role in [
            ("coordinator@ojtkonek.test", "School Coordinator"),
            ("student@ojtkonek.test", "Student"),
            ("company@ojtkonek.test", "Company (verified)"),
            ("pending.company@ojtkonek.test", "Company (pending verification)"),
        ]:
            self.stdout.write(f"  {role:32} {email}")
