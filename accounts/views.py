from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import (
    PROFILE_FORMS,
    AccountEmailForm,
    CompanyRegistrationForm,
    LoginForm,
    StudentRegistrationForm,
)
from .models import Company, SchoolCoordinator, Student, User


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------
def register_choice(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    return render(request, "accounts/register_choice.html")


def _register(request, form_class, template, success_message):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")
    if request.method == "POST":
        form = form_class(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, success_message)
            return redirect("accounts:login")
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = form_class()
    return render(request, template, {"form": form})


def register_student(request):
    if not SchoolCoordinator.objects.exists():
        messages.warning(request, "Student registration opens once a school coordinator has been added.")
    return _register(
        request,
        StudentRegistrationForm,
        "accounts/register_student.html",
        "Your student account was created. You can now log in.",
    )


def register_company(request):
    return _register(
        request,
        CompanyRegistrationForm,
        "accounts/register_company.html",
        "Your company account was created. A school coordinator must verify it before you can publish postings.",
    )


# --------------------------------------------------------------------------
# Login / Logout
# --------------------------------------------------------------------------
def login_view(request):
    if request.user.is_authenticated:
        return redirect("accounts:dashboard")

    next_url = request.POST.get("next") or request.GET.get("next") or ""
    if request.method == "POST":
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)  # also updates last_login_at
            messages.success(request, f"Welcome, {user.display_name}!")
            if next_url and url_has_allowed_host_and_scheme(next_url, {request.get_host()}, request.is_secure()):
                return redirect(next_url)
            return redirect("accounts:dashboard")
    else:
        form = LoginForm(request)
    return render(request, "accounts/login.html", {"form": form, "next": next_url})


@require_POST
def logout_view(request):
    logout(request)  # ends the session
    messages.success(request, "You have been logged out.")
    return redirect("accounts:login")


# --------------------------------------------------------------------------
# Role-based dashboards
# --------------------------------------------------------------------------
@login_required
def dashboard_redirect(request):
    """After login every user lands here and is sent to their own role's dashboard."""
    destinations = {
        User.Role.STUDENT: "accounts:student_dashboard",
        User.Role.COMPANY: "accounts:company_dashboard",
        User.Role.COORDINATOR: "accounts:coordinator_dashboard",
    }
    return redirect(destinations[request.user.role])


@role_required(User.Role.STUDENT)
def student_dashboard(request):
    from postings.models import OjtPosting

    OjtPosting.close_expired()
    student = request.user.profile
    recent_postings = (
        OjtPosting.objects.visible_to_students().select_related("field", "company").order_by("-published_at")[:5]
    )
    return render(request, "dashboards/student_dashboard.html", {
        "student": student,
        "recent_postings": recent_postings,
    })


@role_required(User.Role.COMPANY)
def company_dashboard(request):
    from postings.models import OjtPosting

    OjtPosting.close_expired()
    company = request.user.profile
    postings = company.postings.select_related("field")
    return render(request, "dashboards/company_dashboard.html", {
        "company": company,
        "open_count": postings.filter(status=OjtPosting.Status.OPEN).count(),
        "draft_count": postings.filter(status=OjtPosting.Status.DRAFT).count(),
        "recent_postings": postings[:5],
    })


def _open_postings_count():
    from postings.models import OjtPosting

    return OjtPosting.objects.visible_to_students().count()


@role_required(User.Role.COORDINATOR)
def coordinator_dashboard(request):
    coordinator = request.user.profile
    students = coordinator.students.select_related("user") if coordinator else Student.objects.none()
    context = {
        "coordinator": coordinator,
        "students": students,
        "student_count": students.count(),
        "pending_companies": Company.objects.filter(verification_status=Company.VerificationStatus.PENDING),
        "verified_count": Company.objects.filter(verification_status=Company.VerificationStatus.VERIFIED).count(),
        "open_postings_count": _open_postings_count(),
    }
    return render(request, "dashboards/coordinator_dashboard.html", context)


# --------------------------------------------------------------------------
# Profile — always request.user, so users only ever see/edit their own (BR-05)
# --------------------------------------------------------------------------
@login_required
def profile_view(request):
    return render(request, "accounts/profile.html", {"profile": request.user.profile})


@login_required
def profile_edit(request):
    user = request.user
    profile = user.profile
    ProfileForm = PROFILE_FORMS[user.role]

    if profile is None:
        messages.error(request, "Your account has no profile yet. Please contact the administrator.")
        return redirect("accounts:dashboard")

    if request.method == "POST":
        account_form = AccountEmailForm(request.POST, instance=user, prefix="account")
        profile_form = ProfileForm(request.POST, instance=profile, prefix="profile")
        if account_form.is_valid() and profile_form.is_valid():
            account_form.save()
            profile_form.save()
            messages.success(request, "Your profile has been updated.")
            if user.role == User.Role.COMPANY and profile.verification_status == Company.VerificationStatus.REJECTED:
                profile.resubmit()
                messages.info(request, "Your company was sent back to the coordinators for verification.")
            return redirect("accounts:profile")
        messages.error(request, "Please fix the errors below and try again.")
    else:
        account_form = AccountEmailForm(instance=user, prefix="account")
        profile_form = ProfileForm(instance=profile, prefix="profile")

    return render(
        request,
        "accounts/profile_edit.html",
        {"account_form": account_form, "profile_form": profile_form},
    )
