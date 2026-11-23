from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User
from postings.models import OjtPosting

from .forms import ApplicationForm, DecisionForm
from .models import Application

STUDENT = User.Role.STUDENT
COMPANY = User.Role.COMPANY
COORDINATOR = User.Role.COORDINATOR


def _status_tabs(queryset, status):
    counts = {s: queryset.filter(status=s).count() for s in Application.Status.values}
    counts["all"] = sum(counts.values())
    tabs = [("all", "All")] + list(Application.Status.choices)
    return [(v, label, counts[v]) for v, label in tabs]


# --------------------------------------------------------------------------
# Student: apply, view, edit, withdraw (F-07)
# --------------------------------------------------------------------------
@role_required(STUDENT)
def apply(request, posting_id):
    student = request.user.profile
    posting = get_object_or_404(OjtPosting.objects.select_related("company", "field"), pk=posting_id)

    try:
        Application.check_can_apply(student, posting)
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
        existing = Application.objects.filter(student=student, posting=posting).first()
        if existing:
            return redirect("applications:detail", application_id=existing.pk)
        if not student.resume_url:
            return redirect("accounts:profile_edit")
        return redirect("postings:browse")

    if request.method == "POST":
        form = ApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            application.student = student
            application.posting = posting
            application.resume_url_snapshot = student.resume_url  # BR-09
            application.save()
            messages.success(request, f"Your application to {posting.company.company_name} was submitted.")
            return redirect("applications:detail", application_id=application.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = ApplicationForm()
    return render(request, "applications/apply.html", {"form": form, "posting": posting, "student": student})


@role_required(STUDENT)
def my_applications(request):
    student = request.user.profile
    applications = student.applications.select_related("posting", "posting__company", "posting__field")
    status = request.GET.get("status", "all")
    tabs = _status_tabs(applications, status)
    if status in Application.Status.values:
        applications = applications.filter(status=status)
    else:
        status = "all"
    return render(request, "applications/my_applications.html",
                  {"applications": applications, "tabs": tabs, "status": status})


def _own_application(request, application_id):
    """BR-05: students only reach their own applications."""
    return get_object_or_404(
        Application.objects.select_related("posting", "posting__company", "posting__field"),
        pk=application_id, student=request.user.profile,
    )


@role_required(STUDENT)
def application_detail(request, application_id):
    application = _own_application(request, application_id)
    return render(request, "applications/application_detail.html", {"application": application})


@role_required(STUDENT)
def application_edit(request, application_id):
    application = _own_application(request, application_id)
    if not application.can_edit:
        messages.error(request, "You can only edit an application while it is still Pending.")
        return redirect("applications:detail", application_id=application.pk)
    if request.method == "POST":
        form = ApplicationForm(request.POST, instance=application)
        if form.is_valid():
            form.save()
            messages.success(request, "Your cover letter was updated.")
            return redirect("applications:detail", application_id=application.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = ApplicationForm(instance=application)
    return render(request, "applications/apply.html",
                  {"form": form, "posting": application.posting, "application": application})


@require_POST
@role_required(STUDENT)
def withdraw(request, application_id):
    """'Delete' for applications: BR-06 keeps the record, so it is marked Withdrawn (BR-23)."""
    application = _own_application(request, application_id)
    try:
        application.withdraw()
        messages.success(request, "Your application was withdrawn.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("applications:detail", application_id=application.pk)


# --------------------------------------------------------------------------
# Company: track applicants for own postings (F-08)
# --------------------------------------------------------------------------
def _company_application(request, application_id):
    """BR-24: a company only reaches applications to its own postings."""
    return get_object_or_404(
        Application.objects.select_related("student", "student__user", "posting", "posting__field"),
        pk=application_id, posting__company=request.user.profile,
    )


@role_required(COMPANY)
def all_applicants(request):
    company = request.user.profile
    applications = Application.objects.filter(posting__company=company).select_related(
        "student", "posting"
    ).exclude(status=Application.Status.WITHDRAWN)
    status = request.GET.get("status", "all")
    tabs = [t for t in _status_tabs(applications, status) if t[0] != "withdrawn"]
    if status in Application.Status.values:
        applications = applications.filter(status=status)
    else:
        status = "all"
    return render(request, "applications/applicants.html",
                  {"applications": applications, "tabs": tabs, "status": status, "posting": None})


@role_required(COMPANY)
def posting_applicants(request, posting_id):
    posting = get_object_or_404(OjtPosting, pk=posting_id, company=request.user.profile)
    applications = posting.applications.select_related("student", "posting")
    status = request.GET.get("status", "all")
    tabs = _status_tabs(applications, status)
    if status in Application.Status.values:
        applications = applications.filter(status=status)
    else:
        status = "all"
    return render(request, "applications/applicants.html",
                  {"applications": applications, "tabs": tabs, "status": status, "posting": posting})


@role_required(COMPANY)
def applicant_detail(request, application_id):
    application = _company_application(request, application_id)
    return render(request, "applications/applicant_detail.html",
                  {"application": application, "form": DecisionForm()})


@require_POST
@role_required(COMPANY)
def decide(request, application_id):
    application = _company_application(request, application_id)
    form = DecisionForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please fix the errors below.")
        return render(request, "applications/applicant_detail.html", {"application": application, "form": form})

    action, remarks = form.cleaned_data["action"], form.cleaned_data["remarks"]
    name = f"{application.student.first_name} {application.student.last_name}"
    try:
        if action == "review":
            application.mark_under_review()
            messages.success(request, f"{name}'s application is now Under Review.")
        elif action == "accept":
            closed = application.accept(remarks)
            messages.success(request, f"You accepted {name}.")
            if closed:
                messages.info(request, "All slots are now filled, so the posting was closed automatically.")
        else:
            application.reject(remarks)
            messages.success(request, f"You rejected {name}'s application.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("applications:applicant_detail", application_id=application.pk)


# --------------------------------------------------------------------------
# Coordinator: monitor applications of assigned students (F-10, read-only)
# --------------------------------------------------------------------------
@role_required(COORDINATOR)
def student_applications(request):
    coordinator = request.user.profile
    students = coordinator.students.annotate(
        total=Count("applications"),
        active=Count("applications", filter=Q(applications__status__in=Application.ACTIVE)),
        accepted=Count("applications", filter=Q(applications__status=Application.Status.ACCEPTED)),
    )
    applications = Application.objects.filter(student__coordinator=coordinator).select_related(
        "student", "posting", "posting__company"
    )
    selected = request.GET.get("student")
    if selected and selected.isdigit():
        applications = applications.filter(student_id=int(selected))
    return render(request, "applications/coordinator_overview.html",
                  {"students": students, "applications": applications, "selected": selected})
