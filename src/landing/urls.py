from django.urls import path
from django.views.generic import RedirectView

app_name = 'landing'

urlpatterns = [
    path('', RedirectView.as_view(url='/'), name='index'),
]
