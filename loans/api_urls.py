from django.urls import path
from . import api_views

app_name = "loans_api"

urlpatterns = [
    path("", api_views.loan_list, name="loan-list"),
    path("<uuid:pk>/", api_views.loan_detail, name="loan-detail"),
    path("<uuid:pk>/cancel/", api_views.loan_cancel, name="loan-cancel"),
    path("<uuid:pk>/approve/", api_views.loan_approve, name="loan-approve"),
    path("<uuid:pk>/reject/", api_views.loan_reject, name="loan-reject"),
    path("<uuid:pk>/mark-borrowed/", api_views.loan_mark_borrowed, name="loan-mark-borrowed"),
    path("<uuid:pk>/request-return/", api_views.loan_request_return, name="loan-request-return"),
    path("<uuid:pk>/complete/", api_views.loan_complete, name="loan-complete"),
]
