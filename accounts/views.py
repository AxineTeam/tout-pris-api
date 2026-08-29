from drf_spectacular.utils import extend_schema
from rest_framework import generics
from rest_framework.response import Response

from accounts.serializers import MeSerializer, MeUpdateSerializer


class MeView(generics.GenericAPIView):
    serializer_class = MeUpdateSerializer

    @extend_schema(request=MeUpdateSerializer, responses={200: MeSerializer})
    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        return Response(MeSerializer(serializer.save()).data)
