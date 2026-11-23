"""BR-18: close Open postings whose application deadline has passed.
Run daily (e.g. Windows Task Scheduler / cron):  python manage.py close_expired_postings
The posting pages also run this check each time they load."""
from django.core.management.base import BaseCommand

from postings.models import OjtPosting


class Command(BaseCommand):
    help = "Close Open OJT postings whose application deadline has passed."

    def handle(self, *args, **options):
        count = OjtPosting.close_expired()
        self.stdout.write(self.style.SUCCESS(f"Closed {count} expired posting(s)."))
