
from rest_framework import serializers

from vdi.serializers import VDISerializer
from vcenter.models import VCenter


class VCenterSerializer(serializers.ModelSerializer):
    vdi = VDISerializer(read_only=True, required=False)

    class Meta:
        model = VCenter

        fields = ('id', 'vdi', 'address', 'user', 'password', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_validation_exclusions(self, *args, **kwargs):
        exclusions = super(VCenterSerializer, self).get_validation_exclusions()

        return exclusions + ['vdi']
