from django.urls import path
from .views.projects import StudioProjectListCreateView, StudioProjectDetailView, InterviewView
from .views.pipeline import PipelineStateView, PipelineRunView, PipelineEventsView
from .views.files import FileTreeView, FileDetailView

app_name = 'studio'

urlpatterns = [
    path('projects/', StudioProjectListCreateView.as_view(), name='project_list_create'),
    path('projects/<uuid:id>/', StudioProjectDetailView.as_view(), name='project_detail'),
    path('projects/<uuid:id>/interview/', InterviewView.as_view(), name='interview'),
    path('projects/<uuid:id>/pipeline/', PipelineStateView.as_view(), name='pipeline_state'),
    path('projects/<uuid:id>/run/', PipelineRunView.as_view(), name='pipeline_run'),
    path('projects/<uuid:id>/events/', PipelineEventsView.as_view(), name='pipeline_events'),
    path('projects/<uuid:id>/files/', FileTreeView.as_view(), name='file_tree'),
    path('projects/<uuid:id>/files/<int:file_id>/', FileDetailView.as_view(), name='file_detail'),
]
