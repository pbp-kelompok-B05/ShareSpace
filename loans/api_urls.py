from django.urls import path
from .api_views import LoanRequestViewSet

app_name = "loans_api"

urlpatterns = [
    path("", LoanRequestViewSet.as_view({"get": "list", "post": "create"}), name="loan-list"),
    path("<uuid:pk>/", LoanRequestViewSet.as_view({"get": "retrieve", "patch": "partial_update"}), name="loan-detail"),
    path("<uuid:pk>/cancel/", LoanRequestViewSet.as_view({"post": "cancel"}), name="loan-cancel"),
    path("<uuid:pk>/approve/", LoanRequestViewSet.as_view({"post": "approve"}), name="loan-approve"),
    path("<uuid:pk>/reject/", LoanRequestViewSet.as_view({"post": "reject"}), name="loan-reject"),
    path("<uuid:pk>/mark-borrowed/", LoanRequestViewSet.as_view({"post": "mark_borrowed"}), name="loan-mark-borrowed"),
    path("<uuid:pk>/request-return/", LoanRequestViewSet.as_view({"post": "request_return"}), name="loan-request-return"),
    path("<uuid:pk>/complete/", LoanRequestViewSet.as_view({"post": "complete"}), name="loan-complete"),
]
