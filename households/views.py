from rest_framework import generics

from households.models import Household
from households.serializers import HouseholdSerializer


class HouseholdListView(generics.ListAPIView):
    serializer_class = HouseholdSerializer

    def get_queryset(self):
        return Household.objects.filter(members__user=self.request.user).order_by("created_at")
