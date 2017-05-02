
from rest_framework import serializers

from authentication.serializers import AccountSerializer
from vdi.models import VDI


class VDISerializer(serializers.ModelSerializer):
    author = AccountSerializer(read_only=True, required=False)

    class Meta:
        model = VDI

        fields = ('id', 'author', 'address', 'user', 'domain', 'password', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')

    def get_validation_exclusions(self, *args, **kwargs):
        exclusions = super(VDISerializer, self).get_validation_exclusions()

        return exclusions + ['author']
