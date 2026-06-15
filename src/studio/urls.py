from django.urls import path
from .views.projects import StudioProjectListCreateView, StudioProjectDetailView, InterviewView

app_name = 'studio'

urlpatterns = [
    path('projects/', StudioProjectListCreateView.as_view(), name='project_list_create'),
    path('projects/<uuid:id>/', StudioProjectDetailView.as_view(), name='project_detail'),
    path('projects/<uuid:id>/interview/', InterviewView.as_view(), name='interview'),
]
