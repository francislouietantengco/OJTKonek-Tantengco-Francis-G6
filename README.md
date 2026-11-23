# OJTKonek-Tantengco-Francis-G6

**OJT Konek** connects IT and CS students to On-the-Job Training (OJT) and internship opportunities.
Students find and apply for OJT postings, companies publish openings and review applicants, and school
coordinators verify companies and monitor their students.

Built with full-stack Django (templates) and PostgreSQL on Supabase.

## Core feature: OJT Postings & Applications

The main thing OJT Konek does is match students with OJT slots. This increment delivers that flow end to end:

1. **Company verification:** a coordinator reviews each new company and verifies or rejects it (with a reason).
   Only verified companies can publish postings.
2. **OJT postings:** a verified company creates, edits, publishes and closes postings
   (title, field, location, duration, slots, deadline).
3. **Search & apply:** a student searches open postings by keyword, field, location and duration,
   applies with a cover letter and resume link, edits the cover letter while Pending, or withdraws.
4. **Applicant tracking:** the company reviews applicants, marks them Under Review, then accepts or
   rejects them (remarks are required to reject). When all slots are filled, the posting closes automatically.
5. **Oversight:** a coordinator sees the applications of the students assigned to them.

| Role | What they can do |
|---|---|
| Student | Browse and search postings, apply, view/edit/withdraw own applications |
| Company | Create/edit/publish/close own postings, review/accept/reject applicants to own postings |
| School Coordinator | Verify or reject companies, view postings, monitor assigned students' applications |

Business rules from the SDD that are enforced include BR-09 to BR-26 (resume required, one application
per posting, max 5 active applications, valid status flow, slot limits, deadline and duration checks).
Records are never physically deleted (BR-06): postings are **closed** and applications are **withdrawn**.

## Setup

```bash
git clone https://github.com/francislouietantengco/OJTKonek-Tantengco-Francis-G6.git
cd OJTKonek-Tantengco-Francis-G6

python -m venv venv
venv\Scripts\activate            # Windows  (macOS/Linux: source venv/bin/activate)
pip install -r requirements.txt

copy .env.example .env           # macOS/Linux: cp .env.example .env
```

Edit `.env`:

- `SECRET_KEY`: generate one with
  `python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"`
  and wrap it in single quotes.
- `DATABASE_URL`: your Supabase **Session pooler** connection string (Connect → Direct → Session pooler).

Then:

```bash
python manage.py migrate
python manage.py seed_demo       # optional: demo accounts + sample postings
python manage.py createsuperuser # optional: admin account for /admin
python manage.py runserver 8001
```

Open http://127.0.0.1:8001/

### Demo accounts (`seed_demo`)

All use the password `OjtKonek2026`.

| Role | Email |
|---|---|
| School Coordinator | coordinator@ojtkonek.test |
| Student | student@ojtkonek.test |
| Company (verified) | company@ojtkonek.test |
| Company (pending) | pending.company@ojtkonek.test |

### Other commands

```bash
python manage.py test                     # run the test suite
python manage.py create_coordinator --email ... --first-name ... --last-name ...
python manage.py close_expired_postings   # close postings past their deadline (also runs on page load)
```

## Project structure

```
accounts/       users, profiles, registration, login, dashboards, company verification
postings/       fields + OJT postings (company management, student search)
applications/   applications (apply, withdraw, applicant tracking, coordinator overview)
templates/      Django templates for every page
docs/           completion reports
```

## Branching strategy

- `main` – stable releases only, no direct commits
- `develop` – integration branch, created from `main`
- `feature/<name>`, `fix/<name>`, `docs/<name>` – one branch per change, created from `develop`

Workflow: branch → Pull Request into `develop` → when an increment is done, Pull Request from `develop` into `main`.
Merged branches are kept.