from django.urls import path
from django.views.generic import RedirectView
from . import views

app_name = 'landing'

urlpatterns = [
    path('', RedirectView.as_view(url='/'), name='index'),
    path('api-docs/', views.api_docs, name='api_docs'),
    path('ide/', views.ide_integrations, name='ide_integrations'),
]
