from django.db.models import Q
from rest_framework import generics

from households.models import Household
from households.serializers import HouseholdSerializer


class HouseholdListView(generics.ListAPIView):
    serializer_class = HouseholdSerializer

    def get_queryset(self):
        return (
            Household.objects.filter(members__user=self.request.user)
            .alias(personal=Q(personal_of__isnull=False))
            .order_by("-personal", "created_at")
        )
