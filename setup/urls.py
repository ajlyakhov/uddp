from django.urls import path
from .views import RootView, SetupWizardView, TestPublishView

urlpatterns = [
    path('', RootView.as_view(), name='root'),
    path('setup/', SetupWizardView.as_view(), name='setup_wizard'),
    path('test/', TestPublishView.as_view(), name='test_publish'),
]
