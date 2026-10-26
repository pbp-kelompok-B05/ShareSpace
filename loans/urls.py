from django.urls import path
from .views import *

app_name = "loans"

urlpatterns = [
    path("", loan_list, name="list"),
    path("data/", loan_list_data, name="data"),
]