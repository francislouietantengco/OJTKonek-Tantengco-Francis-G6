from django.contrib import admin
from django.urls import include, path
from django.views.generic import RedirectView

admin.site.site_header = "OJT Konek Administration"
admin.site.site_title = "OJT Konek Admin"

urlpatterns = [
    path("", RedirectView.as_view(pattern_name="accounts:dashboard", permanent=False)),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
]
