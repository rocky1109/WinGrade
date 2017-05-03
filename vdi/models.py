from django.db import models

from authentication.models import Account


class VDI(models.Model):
    author = models.ForeignKey(Account)
    address = models.TextField()
    user = models.TextField()
    domain = models.TextField()
    password = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __unicode__(self):
        return '[{0}]{1}'.format(self.id, self.address)
