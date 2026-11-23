from django.urls import path

from . import views

app_name = "applications"

urlpatterns = [
    # Student
    path("", views.my_applications, name="my_applications"),
    path("apply/<int:posting_id>/", views.apply, name="apply"),
    path("<int:application_id>/", views.application_detail, name="detail"),
    path("<int:application_id>/edit/", views.application_edit, name="edit"),
    path("<int:application_id>/withdraw/", views.withdraw, name="withdraw"),
    # Company
    path("applicants/", views.all_applicants, name="all_applicants"),
    path("applicants/posting/<int:posting_id>/", views.posting_applicants, name="posting_applicants"),
    path("applicants/<int:application_id>/", views.applicant_detail, name="applicant_detail"),
    path("applicants/<int:application_id>/decide/", views.decide, name="decide"),
    # Coordinator
    path("students/", views.student_applications, name="student_applications"),
]
