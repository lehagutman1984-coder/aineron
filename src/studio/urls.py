from django.urls import path, re_path
from .views.projects import StudioProjectListCreateView, StudioProjectDetailView, InterviewView, CloneView, TemplateListView
from .views.pipeline import (
    EstimateView, PipelineStateView, PipelineRunView, PipelineEventsView,
    PipelinePauseView, PipelineResumeView, PreviewProxyView, ContextChatView,
    ApproveStepView,
)
from .views.files import FileTreeView, FileDetailView, FileDiffView, CommitHistoryView, RollbackView

app_name = 'studio'

urlpatterns = [
    path('projects/', StudioProjectListCreateView.as_view(), name='project_list_create'),
    path('projects/<uuid:id>/', StudioProjectDetailView.as_view(), name='project_detail'),
    path('projects/<uuid:id>/interview/', InterviewView.as_view(), name='interview'),
    path('projects/<uuid:id>/estimate/', EstimateView.as_view(), name='pipeline_estimate'),
    path('projects/<uuid:id>/pipeline/', PipelineStateView.as_view(), name='pipeline_state'),
    path('projects/<uuid:id>/run/', PipelineRunView.as_view(), name='pipeline_run'),
    path('projects/<uuid:id>/events/', PipelineEventsView.as_view(), name='pipeline_events'),
    path('projects/<uuid:id>/pause/', PipelinePauseView.as_view(), name='pipeline_pause'),
    path('projects/<uuid:id>/resume/', PipelineResumeView.as_view(), name='pipeline_resume'),
    path('projects/<uuid:id>/chat/', ContextChatView.as_view(), name='context_chat'),
    path('projects/<uuid:id>/approve/', ApproveStepView.as_view(), name='approve_step'),
    path('projects/<uuid:id>/files/', FileTreeView.as_view(), name='file_tree'),
    path('projects/<uuid:id>/files/<int:file_id>/', FileDetailView.as_view(), name='file_detail'),
    path('projects/<uuid:id>/files/<int:file_id>/diff/', FileDiffView.as_view(), name='file_diff'),
    path('projects/<uuid:id>/commits/', CommitHistoryView.as_view(), name='commit_history'),
    path('projects/<uuid:id>/rollback/<int:version_id>/', RollbackView.as_view(), name='rollback'),
    path('clone/', CloneView.as_view(), name='clone'),
    path('templates/', TemplateListView.as_view(), name='template_list'),
    # Preview proxy: proxies HTTP to sandbox container; ?path= is the sub-path
    re_path(r'^projects/(?P<id>[0-9a-f-]{36})/preview/(?P<path>.*)$', PreviewProxyView.as_view(), name='preview_proxy'),
]
