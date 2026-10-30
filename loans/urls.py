from django.urls import path
from .views import *

app_name = "loans"

urlpatterns = [
    path("", loan_list, name="list"),
    path("data/", loan_list_data, name="data"),
    path("incoming/", loan_lender_list, name="lender_list"),
    path("incoming/data/", loan_lender_list_data, name="lender_data"),
    path("create/<int:item_id>/", loan_create, name="create"),
    path("detail/<uuid:pk>/", loan_detail, name="detail"),
    path("edit/<uuid:pk>/", loan_update, name="update"),
    path("cancel/<uuid:pk>/", loan_cancel, name="cancel"),
    path("approve/<uuid:pk>/", loan_approve, name="approve"),
    path("reject/<uuid:pk>/", loan_reject, name="reject"),
    path("borrowed/<uuid:pk>/", loan_mark_borrowed, name="mark_borrowed"),
    path("return/<uuid:pk>/", loan_request_return, name="request_return"),
    path("complete/<uuid:pk>/", loan_complete, name="complete"),
]
