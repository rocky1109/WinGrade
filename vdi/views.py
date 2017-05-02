from rest_framework import permissions, viewsets
from rest_framework.response import Response

from vdi.models import VDI
from vdi.permissions import IsAuthorOfVDI
from vdi.serializers import VDISerializer


class VDIViewSet(viewsets.ModelViewSet):

    queryset = VDI.objects.order_by('-created_at')
    serializer_class = VDISerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return (permissions.AllowAny(),)
        return (permissions.IsAuthenticated(), IsAuthorOfVDI(),)

    def perform_create(self, serializer):
        instance = serializer.save(author=self.request.user)

        return super(VDIViewSet, self).perform_create(serializer)


class AccountVDIsViewSet(viewsets.ViewSet):

    queryset = VDI.objects.select_related('author').order_by('-created_at')
    serializer_class = VDISerializer

    def list(self, request, account_username=None):
        queryset = self.queryset.filter(author__username=account_username)
        serializer = self.serializer_class(queryset, many=True)

        return Response(serializer.data)
