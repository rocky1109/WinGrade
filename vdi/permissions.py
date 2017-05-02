
from rest_framework import permissions


class IsAuthorOfVDI(permissions.BasePermission):

    def has_object_permission(self, request, view, vdi):
        if request.user:
            return vdi.author == request.user
        return False
