from django.urls import path

from . import views

app_name = "postings"

urlpatterns = [
    # Students / coordinators
    path("", views.browse, name="browse"),
    path("<int:posting_id>/", views.posting_detail, name="detail"),
    # Company
    path("mine/", views.my_postings, name="my_postings"),
    path("mine/new/", views.posting_create, name="create"),
    path("mine/<int:posting_id>/", views.manage_detail, name="manage_detail"),
    path("mine/<int:posting_id>/edit/", views.posting_edit, name="edit"),
    path("mine/<int:posting_id>/publish/", views.posting_publish, name="publish"),
    path("mine/<int:posting_id>/close/", views.posting_close, name="close"),
]
