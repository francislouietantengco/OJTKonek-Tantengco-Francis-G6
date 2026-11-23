from django.urls import path

from . import verification_views, views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_choice, name="register"),
    path("register/student/", views.register_student, name="register_student"),
    path("register/company/", views.register_company, name="register_company"),
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("dashboard/", views.dashboard_redirect, name="dashboard"),
    path("dashboard/student/", views.student_dashboard, name="student_dashboard"),
    path("dashboard/company/", views.company_dashboard, name="company_dashboard"),
    path("dashboard/coordinator/", views.coordinator_dashboard, name="coordinator_dashboard"),
    path("profile/", views.profile_view, name="profile"),
    path("profile/edit/", views.profile_edit, name="profile_edit"),
    # F-04 Company Verification (coordinator)
    path("companies/", verification_views.company_list, name="company_list"),
    path("companies/<int:company_id>/", verification_views.company_detail, name="company_detail"),
    path("companies/<int:company_id>/verify/", verification_views.company_verify, name="company_verify"),
    path("companies/<int:company_id>/reject/", verification_views.company_reject, name="company_reject"),
]
