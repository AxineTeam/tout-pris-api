from django.urls import path

from households.views import HouseholdListView

urlpatterns = [path("households/", HouseholdListView.as_view(), name="households")]
