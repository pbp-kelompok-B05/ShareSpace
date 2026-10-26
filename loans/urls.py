from django.urls import path
from .views import *

app_name = "loans"

urlpatterns = [
    path("", loan_list, name="list"),
    path("data/", loan_list_data, name="data"),
    path("create/<int:item_id>/", loan_create, name="create"),
    path("detail/<uuid:pk>/", loan_detail, name="detail"),
]