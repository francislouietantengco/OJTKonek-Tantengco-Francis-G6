# OJT Konek

Connecting IT and CS students to On-the-Job Training and internship opportunities.
CSIT317 – G2 · Tantengco, Francis Louie A.

**Phase 1: Account Feature.** Registration, login/logout, role-based dashboards and profile management for three roles: **Student**, **Company** and **School Coordinator**.

## Tech stack
- Full-stack Django 5.2 (Django templates for the frontend)
- PostgreSQL via Supabase (SQLite is not used)

## What's implemented

| Requirement | Where |
|---|---|
| Registration form for students and companies | `accounts/forms.py`, `/accounts/register/` |
| Validation: required fields, valid email, unique email (BR-01), unique student number (BR-07), matching passwords | `StudentRegistrationForm`, `CompanyRegistrationForm` |
| Password rules: at least 8 characters, at least one letter and one number, hashed (BR-02) | `settings.AUTH_PASSWORD_VALIDATORS`, `accounts/validators.py` |
| Login by email, error on invalid credentials | `LoginForm`, `login_view` |
| Account locked for 15 minutes after 5 failed logins (BR-03) | `User.register_failed_login()` |
| Deactivated accounts can't log in (BR-04) | `User.is_active` / `account_status` |
| Logout ends the session (POST only) | `logout_view` |
| `@login_required` and `@role_required` protect pages | `accounts/decorators.py` |
| Each role is sent to its own dashboard and can't open another role's dashboard by URL | `dashboard_redirect`, `role_required` |
| View and edit own profile only | `profile_view`, `profile_edit` (always uses `request.user`) |
| New companies start as **Pending** (BR-10) | `Company.verification_status` |
| No physical deletes in admin (BR-06) | `accounts/admin.py` |

Tables follow the SDD data dictionary: `users`, `students`, `companies`, `school_coordinators`.

## Setup

```bash
# 1. Clone and enter the project
git clone https://github.com/<your-username>/OJTKonek-Tantengco-Francis-G2.git
cd OJTKonek-Tantengco-Francis-G2

# 2. Create and activate a virtual environment
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS / Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create your .env file from the example, then fill in your values
copy .env.example .env         # Windows
# cp .env.example .env         # macOS / Linux
```

### Supabase connection
1. Create a project at supabase.com.
2. Click **Connect** at the top of the dashboard and copy the **Session pooler** connection string (URI).
3. Paste it into `.env` as `DATABASE_URL`, replacing `[YOUR-PASSWORD]` with your database password.
4. Generate a secret key and paste it into `SECRET_KEY`:
   ```bash
   python -c "from django.core.management.utils import get_random_secret_key as k; print(k())"
   ```

### Run it
```bash
python manage.py migrate
python manage.py createsuperuser          # system admin (gets the Coordinator role)
python manage.py create_coordinator --email maria@school.edu --first-name Maria --last-name Santos
python manage.py runserver
```
Open http://127.0.0.1:8000/

> Students choose a coordinator when they register (BR-08), so create at least one coordinator first.
> Coordinators don't self-register. Create them with `create_coordinator` or in `/admin`.

### Run the tests
```bash
python manage.py test accounts
```

## Project structure
```
config/            settings, root urls
accounts/          models, forms, views, decorators, admin, tests
  management/commands/create_coordinator.py
templates/         base.html, accounts/, dashboards/
static/css/        style.css
```
