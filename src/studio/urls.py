from django.urls import path, re_path
from .views.projects import (
    StudioProjectListCreateView, StudioProjectDetailView, InterviewView, CloneView,
    TemplateListView, PublishTemplateView, CollaboratorView, ProjectSettingsView,
    TimelineView, BranchFromVersionView, ScreenshotView, GithubExportView,
    NotificationPrefsView, DeviationView, ModelsCatalogView,
)
from .views.pipeline import (
    EstimateView, PipelineStateView, PipelineRunView, PipelineEventsView,
    PipelinePauseView, PipelineResumeView, PreviewProxyView, ContextChatView,
    ApproveStepView, DeployView, SandboxStatusView, PreviewRestartView, ExplainView,
    ConsoleErrorView, PipelineSkipView,
)
from .views.files import FileTreeView, FileDetailView, FileDiffView, CommitHistoryView, RollbackView, ExportView, SearchFilesView

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
    path('projects/<uuid:id>/deploy/', DeployView.as_view(), name='deploy'),
    path('projects/<uuid:id>/sandbox/', SandboxStatusView.as_view(), name='sandbox_status'),
    path('projects/<uuid:id>/files/', FileTreeView.as_view(), name='file_tree'),
    path('projects/<uuid:id>/files/<int:file_id>/', FileDetailView.as_view(), name='file_detail'),
    path('projects/<uuid:id>/files/<int:file_id>/diff/', FileDiffView.as_view(), name='file_diff'),
    path('projects/<uuid:id>/commits/', CommitHistoryView.as_view(), name='commit_history'),
    path('projects/<uuid:id>/rollback/<int:version_id>/', RollbackView.as_view(), name='rollback'),
    path('projects/<uuid:id>/export/', ExportView.as_view(), name='export'),
    path('projects/<uuid:id>/search/', SearchFilesView.as_view(), name='search_files'),
    path('projects/<uuid:id>/settings/', ProjectSettingsView.as_view(), name='project_settings'),
    path('projects/<uuid:id>/publish-template/', PublishTemplateView.as_view(), name='publish_template'),
    path('projects/<uuid:id>/collaborators/', CollaboratorView.as_view(), name='collaborators'),
    path('projects/<uuid:id>/timeline/', TimelineView.as_view(), name='timeline'),
    path('projects/<uuid:id>/branch/<int:version_id>/', BranchFromVersionView.as_view(), name='branch_from_version'),
    path('projects/<uuid:id>/screenshot/', ScreenshotView.as_view(), name='screenshot'),
    path('projects/<uuid:id>/export/github/', GithubExportView.as_view(), name='export_github'),
    path('projects/<uuid:id>/notifications/', NotificationPrefsView.as_view(), name='notification_prefs'),
    path('projects/<uuid:id>/steps/<int:n>/deviation/', DeviationView.as_view(), name='deviation'),
    path('clone/', CloneView.as_view(), name='clone'),
    path('templates/', TemplateListView.as_view(), name='template_list'),
    path('models/', ModelsCatalogView.as_view(), name='models_catalog'),
    path('projects/<uuid:id>/explain/', ExplainView.as_view(), name='explain'),
    path('projects/<uuid:id>/console-error/', ConsoleErrorView.as_view(), name='console_error'),
    path('projects/<uuid:id>/pipeline/skip/', PipelineSkipView.as_view(), name='pipeline_skip'),
    path('projects/<uuid:id>/preview/restart/', PreviewRestartView.as_view(), name='preview_restart'),
    # Preview proxy: proxies HTTP to sandbox container; ?path= is the sub-path
    re_path(r'^projects/(?P<id>[0-9a-f-]{36})/preview/(?P<path>.*)$', PreviewProxyView.as_view(), name='preview_proxy'),
]
