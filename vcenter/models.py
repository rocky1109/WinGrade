from django.db import models

from vdi.models import VDI


class VCenter(models.Model):
    vdi = models.ForeignKey(VDI)
    address = models.TextField()
    user = models.TextField()
    password = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '{0}'.format(self.address)
