"""
Create a School Coordinator account (coordinators do not self-register).

Usage:
    python manage.py create_coordinator --email maria@school.edu --first-name Maria \
        --last-name Santos --department "College of Computer Studies"
You will be asked for the password.
"""
import getpass

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import SchoolCoordinator, User


class Command(BaseCommand):
    help = "Create a School Coordinator account with its profile."

    def add_arguments(self, parser):
        parser.add_argument("--email", required=True)
        parser.add_argument("--first-name", required=True)
        parser.add_argument("--last-name", required=True)
        parser.add_argument("--department", default="College of Computer Studies")
        parser.add_argument("--contact-number", default=None)
        parser.add_argument("--password", help="Leave out to be prompted (recommended).")

    @transaction.atomic
    def handle(self, *args, **opts):
        email = opts["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise CommandError("An account with this email already exists.")

        password = opts["password"]
        if not password:
            password = getpass.getpass("Password: ")
            if password != getpass.getpass("Confirm password: "):
                raise CommandError("Passwords don't match.")
        try:
            validate_password(password)
        except ValidationError as e:
            raise CommandError(" ".join(e.messages))

        user = User.objects.create_user(email=email, password=password, role=User.Role.COORDINATOR)
        SchoolCoordinator.objects.create(
            user=user,
            first_name=opts["first_name"],
            last_name=opts["last_name"],
            department=opts["department"],
            contact_number=opts["contact_number"],
        )
        self.stdout.write(self.style.SUCCESS(f"Coordinator {email} created."))
