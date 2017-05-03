
from django.conf.urls import include, url

from rest_framework_nested import routers

from authentication.views import AccountViewSet, LoginView, LogoutView
from vdi.views import AccountVDIsViewSet, VDIViewSet
from vcenter.views import VDIVCentersViewSet, VCenterViewSet
from WinGrade.views import IndexView

router = routers.SimpleRouter()
router.register(r'accounts', AccountViewSet)
router.register(r'vdis', VDIViewSet)
router.register(r'vcenters', VCenterViewSet)


accounts_router = routers.NestedSimpleRouter(
    router, r'accounts', lookup='account'
)
accounts_router.register(r'vdis', AccountVDIsViewSet)


vdis_router = routers.NestedSimpleRouter(
    router, r'vdis', lookup='vdi'
)
accounts_router.register(r'vdi', VDIVCentersViewSet)


urlpatterns = [
    url(r'^api/v1/', include(router.urls)),
    url(r'^api/v1/', include(accounts_router.urls)),
    url(r'^api/v1/', include(vdis_router.urls)),
    url(r'^api/v1/auth/login/$', LoginView.as_view(), name='login'),
    url(r'^api/v1/auth/logout/$', LogoutView.as_view(), name='logout'),

    url(r'^.*$', IndexView.as_view(), name='index'),
]
