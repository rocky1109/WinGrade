from rest_framework import permissions, viewsets
from rest_framework.response import Response

import defaults
from era.pyview import View
from pyVirtualize.pyvSphere import vSphere

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
        # At the time of creation validate whether the given details for Connection Server are valid.
        vdi_address = serializer.validated_data['address']
        vdi_user = serializer.validated_data['user']
        vdi_password = serializer.validated_data['password']
        vdi_domain = serializer.validated_data['domain']

        view_ = View(host=vdi_address, user=vdi_user, password=vdi_password,
                     domain=vdi_domain, wsdl_file=defaults.VIEW_WSDL_FILE)

        try:
            view_.login()

            instance = serializer.save(author=self.request.user)
            return_ = super(VDIViewSet, self).perform_create(serializer)
            instance = VDI.objects.latest('created_at')

            print(instance)

            vcs = view_.vc.list()

            from vcenter.models import VCenter
            from vcenter.serializers import VCenterSerializer

            for vc in vcs:
                vc_address = vc.serverSpec.serverName
                try:
                    vc_username = vc.serverSpec.userName
                    vc_port = vc.serverSpec.port

                    vcenter = {'address': vc_address, 'user': vc_username, 'password': "", 'vdi': instance}
                    #serialized_vc = VCenterSerializer(data=vcenter)

                    #if serialized_vc.is_valid(raise_exception=True):
                    VCenter.objects.create(**vcenter)

                    print("Added {0} to {1}".format(vc_address, instance))
                except Exception as err:
                    print("Unable to added {0} to {1} [{2}]".format(vc_address, instance, err))

            view_.logout()

            return return_
        except Exception as err:
            print("Unable to log into: {0}".format(vdi_address))
            raise err


class AccountVDIsViewSet(viewsets.ViewSet):

    queryset = VDI.objects.select_related('author').order_by('-created_at')
    serializer_class = VDISerializer

    def list(self, request, account_username=None):
        queryset = self.queryset.filter(author__username=account_username)
        serializer = self.serializer_class(queryset, many=True)

        return Response(serializer.data)
