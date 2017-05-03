from rest_framework import permissions, viewsets
from rest_framework.response import Response

from vcenter.models import VCenter
#from vcenter.permissions import IsAuthorOfVDI
from vcenter.serializers import VCenterSerializer

from rest_framework.decorators import list_route


class VCenterViewSet(viewsets.ModelViewSet):

    queryset = VCenter.objects.order_by('-created_at')
    serializer_class = VCenterSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return (permissions.AllowAny(),)
        return (permissions.IsAuthenticated(),)

    def perform_create(self, serializer):
        instance = serializer.save(author=self.request.user)

        return super(VCenterViewSet, self).perform_create(serializer)


class VDIVCentersViewSet(viewsets.ViewSet):

    queryset = VCenter.objects.select_related('vdi').order_by('-created_at')
    serializer_class = VCenterSerializer

    def list(self, request, vdi_id=None):
        queryset = self.queryset.filter(vdi__id=vdi_id)
        serializer = self.serializer_class(queryset, many=True)

        return Response(serializer.data)
