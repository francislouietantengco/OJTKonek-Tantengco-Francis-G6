from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import role_required
from accounts.models import User

from .forms import PostingForm, PostingSearchForm
from .models import OjtPosting

COMPANY = User.Role.COMPANY
STUDENT = User.Role.STUDENT
COORDINATOR = User.Role.COORDINATOR


def _own_posting(request, posting_id):
    """BR-16: a company can only reach its own postings (404 for anyone else's)."""
    return get_object_or_404(OjtPosting.objects.select_related("field", "company"),
                             pk=posting_id, company=request.user.profile)


# --------------------------------------------------------------------------
# Company: manage own postings (F-05)
# --------------------------------------------------------------------------
@role_required(COMPANY)
def my_postings(request):
    OjtPosting.close_expired()  # BR-18
    company = request.user.profile
    status = request.GET.get("status", "all")
    postings = company.postings.select_related("field")
    counts = {s: postings.filter(status=s).count() for s in OjtPosting.Status.values}
    counts["all"] = sum(counts.values())
    if status in OjtPosting.Status.values:
        postings = postings.filter(status=status)
    else:
        status = "all"
    tabs = [("all", "All")] + list(OjtPosting.Status.choices)
    return render(request, "postings/my_postings.html", {
        "company": company,
        "postings": postings,
        "status": status,
        "tabs": [(v, label, counts[v]) for v, label in tabs],
    })


@role_required(COMPANY)
def posting_create(request):
    company = request.user.profile
    if request.method == "POST":
        form = PostingForm(request.POST, company=company)
        if form.is_valid():
            posting = form.save()
            if "publish" in request.POST:
                try:
                    posting.publish()
                    messages.success(request, f"“{posting.title}” is now open to students.")
                except ValidationError as e:
                    messages.warning(request, f"Saved as a draft. {' '.join(e.messages)}")
            else:
                messages.success(request, f"“{posting.title}” was saved as a draft.")
            return redirect("postings:manage_detail", posting_id=posting.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = PostingForm(company=company)
    return render(request, "postings/posting_form.html", {"form": form, "company": company})


@role_required(COMPANY)
def manage_detail(request, posting_id):
    posting = _own_posting(request, posting_id)
    apps = posting.applications.all()
    summary = {
        "total": apps.exclude(status="withdrawn").count(),
        "pending": apps.filter(status="pending").count(),
        "under_review": apps.filter(status="under_review").count(),
        "accepted": apps.filter(status="accepted").count(),
    }
    return render(request, "postings/manage_detail.html", {"posting": posting, "summary": summary})


@role_required(COMPANY)
def posting_edit(request, posting_id):
    posting = _own_posting(request, posting_id)
    if request.method == "POST":
        form = PostingForm(request.POST, instance=posting)
        if form.is_valid():
            form.save()
            messages.success(request, "Your posting was updated.")
            return redirect("postings:manage_detail", posting_id=posting.pk)
        messages.error(request, "Please fix the errors below and try again.")
    else:
        form = PostingForm(instance=posting)
    return render(request, "postings/posting_form.html", {"form": form, "posting": posting})


@require_POST
@role_required(COMPANY)
def posting_publish(request, posting_id):
    posting = _own_posting(request, posting_id)
    try:
        posting.publish()
        messages.success(request, f"“{posting.title}” is now open to students.")
    except ValidationError as e:
        messages.error(request, " ".join(e.messages))
    return redirect("postings:manage_detail", posting_id=posting.pk)


@require_POST
@role_required(COMPANY)
def posting_close(request, posting_id):
    """'Delete' for postings: BR-06 says records are never physically deleted, so the posting is closed."""
    posting = _own_posting(request, posting_id)
    if posting.status == OjtPosting.Status.CLOSED:
        messages.info(request, "This posting is already closed.")
    else:
        posting.close()
        messages.success(request, f"“{posting.title}” was closed and removed from student search.")
    return redirect("postings:manage_detail", posting_id=posting.pk)


# --------------------------------------------------------------------------
# Students (and coordinators): search and view open postings (F-06)
# --------------------------------------------------------------------------
@role_required(STUDENT, COORDINATOR)
def browse(request):
    OjtPosting.close_expired()  # BR-18
    form = PostingSearchForm(request.GET or None)
    postings = OjtPosting.objects.visible_to_students().select_related("field", "company")

    if form.is_valid():
        data = form.cleaned_data
        if data["q"]:
            q = data["q"].strip()
            postings = postings.filter(
                Q(title__icontains=q) | Q(description__icontains=q)
                | Q(requirements__icontains=q) | Q(company__company_name__icontains=q)
            )
        if data["field"]:
            postings = postings.filter(field=data["field"])
        if data["location"]:
            postings = postings.filter(location__icontains=data["location"].strip())
        if data["duration"]:
            low, high = (int(x) for x in data["duration"].split("-"))
            postings = postings.filter(duration_weeks__gte=low, duration_weeks__lte=high)

    return render(request, "postings/browse.html", {"form": form, "postings": postings.order_by("application_deadline")})


@role_required(STUDENT, COORDINATOR)
def posting_detail(request, posting_id):
    posting = get_object_or_404(
        OjtPosting.objects.visible_to_students().select_related("field", "company"), pk=posting_id
    )
    context = {"posting": posting}
    if request.user.role == STUDENT:
        from applications.models import Application

        student = request.user.profile
        context["existing_application"] = Application.objects.filter(student=student, posting=posting).first()
        try:
            Application.check_can_apply(student, posting)
            context["apply_blocked"] = None
        except ValidationError as e:
            context["apply_blocked"] = " ".join(e.messages)
    return render(request, "postings/posting_detail.html", context)
