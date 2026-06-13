from django.urls import path
from . import views

app_name = 'landing'

urlpatterns = [
    path('', views.index, name='index'),
    path('api-docs/', views.api_docs, name='api_docs'),
    path('ide/', views.ide_integrations, name='ide_integrations'),
]
