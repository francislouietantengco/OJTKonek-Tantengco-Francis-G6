"""F-04 Company Verification: coordinators approve or reject newly registered companies (BR-10)."""
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from .decorators import role_required
from .forms import CompanyRejectForm
from .models import Company, User

STATUS_TABS = [
    ("pending", "Pending"),
    ("verified", "Verified"),
    ("rejected", "Rejected"),
    ("all", "All"),
]


@role_required(User.Role.COORDINATOR)
def company_list(request):
    status = request.GET.get("status", "pending")
    query = request.GET.get("q", "").strip()

    companies = Company.objects.select_related("user", "verified_by").order_by("company_name")
    if status in Company.VerificationStatus.values:
        companies = companies.filter(verification_status=status)
    else:
        status = "all"
    if query:
        companies = companies.filter(
            Q(company_name__icontains=query) | Q(city__icontains=query) | Q(user__email__icontains=query)
        )

    counts = {s: Company.objects.filter(verification_status=s).count() for s in Company.VerificationStatus.values}
    counts["all"] = sum(counts.values())
    tabs = [(value, label, counts[value]) for value, label in STATUS_TABS]
    return render(
        request,
        "verification/company_list.html",
        {"companies": companies, "status": status, "tabs": tabs, "q": query},
    )


@role_required(User.Role.COORDINATOR)
def company_detail(request, company_id):
    company = get_object_or_404(Company.objects.select_related("user", "verified_by"), pk=company_id)
    return render(
        request,
        "verification/company_detail.html",
        {"company": company, "reject_form": CompanyRejectForm()},
    )


@require_POST
@role_required(User.Role.COORDINATOR)
def company_verify(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    if company.is_verified:
        messages.info(request, f"{company.company_name} is already verified.")
    else:
        company.verify(request.user.profile)
        messages.success(request, f"{company.company_name} is now verified and can publish OJT postings.")
    return redirect("accounts:company_detail", company_id=company.pk)


@require_POST
@role_required(User.Role.COORDINATOR)
def company_reject(request, company_id):
    company = get_object_or_404(Company, pk=company_id)
    form = CompanyRejectForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Please enter a reason before rejecting the company.")
        return render(
            request,
            "verification/company_detail.html",
            {"company": company, "reject_form": form},
        )
    company.reject(request.user.profile, form.cleaned_data["rejection_reason"])
    messages.success(request, f"{company.company_name} was rejected. The company can see your reason.")
    return redirect("accounts:company_detail", company_id=company.pk)
