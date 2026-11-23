"""Seed the fields lookup table with common IT/CS OJT fields."""
from django.db import migrations

FIELDS = [
    ("Web Development", "Front-end, back-end and full-stack web work."),
    ("Mobile Development", "Android, iOS and cross-platform apps."),
    ("Networking", "Network setup, administration and support."),
    ("Data and Analytics", "Databases, reporting, data analysis and BI."),
    ("QA/Testing", "Manual and automated software testing."),
    ("Cybersecurity", "Security monitoring, assessment and compliance."),
    ("IT Support", "Help desk, hardware and systems support."),
    ("UI/UX Design", "User research, interface and experience design."),
    ("Software Engineering", "General software development and maintenance."),
    ("Cloud and DevOps", "Cloud infrastructure, CI/CD and automation."),
]


def seed(apps, schema_editor):
    Field = apps.get_model("postings", "Field")
    for name, desc in FIELDS:
        Field.objects.get_or_create(field_name=name, defaults={"description": desc})


def unseed(apps, schema_editor):
    apps.get_model("postings", "Field").objects.filter(field_name__in=[n for n, _ in FIELDS]).delete()


class Migration(migrations.Migration):
    dependencies = [("postings", "0001_initial")]
    operations = [migrations.RunPython(seed, unseed)]
