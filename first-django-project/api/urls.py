from django.urls import path
from .views import hello, add_two_numbers

urlpatterns = [path("hello/", hello), path("add/", add_two_numbers)]
