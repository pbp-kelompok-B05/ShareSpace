from django.urls import path

from review.views import (
    my_reports,
    report_delete,
    report_detail,
    report_item_create,
    report_update,
    report_user_create,
)

app_name = "review"

# Catatan: nama "report_list" dipesan untuk dashboard laporan admin (dipakai navbar).
urlpatterns = [
    path("reports/", my_reports, name="my_reports"),
    path("reports/new/item/<int:item_id>/", report_item_create, name="report_item_create"),
    path("reports/new/user/<str:username>/", report_user_create, name="report_user_create"),
    path("reports/<uuid:pk>/", report_detail, name="report_detail"),
    path("reports/<uuid:pk>/edit/", report_update, name="report_update"),
    path("reports/<uuid:pk>/delete/", report_delete, name="report_delete"),
]
