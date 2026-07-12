from django.urls import path, include
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from api.views.keys import APIKeyListCreateView, APIKeyDeleteView
from api.views.chat import ChatCompletionsView
from api.views.anthropic import AnthropicMessagesView
from api.views.images import ImageGenerationsView
from api.views.prompt_enhance import ImagePromptEnhanceView
from api.views.image_compare import ImageCompareView
from api.views.models_list import ModelsListView
from api.views.catalog import CategoryListView, NetworkListView, NetworkDetailView
from api.views.chats import (
    ChatListCreateView, ChatDetailView, SendMessageView, MessageStatusView,
    StreamMessageView, RegenerateView,
)
from api.views.chat_search import ChatSearchView
from api.views.chat_export import ChatExportView
from api.views.uploads import ChatFileUploadView, ReferenceImageUploadView
from api.views.auth import MeView, LoginView, LogoutView, RegisterView, VerifyEmailView, ResendVerificationView
from api.views.teams import (
    OrgListCreateView, OrgDetailView,
    OrgMemberListView, OrgMemberDeleteView,
    OrgInviteListCreateView, InviteAcceptView,
    OrgTgTokenView, OrgTgGroupsView,
)
from api.views.invoices import InvoiceListCreateView
from api.views.usage import UsageStatsView
from api.views.blog import BlogCategoryListView, BlogPostListView, BlogPostDetailView
from api.views.billing import (
    TariffListView, TariffPayView, PageSaleSettingsView,
    BuyPagesView, PaymentHistoryView, ApplyPromoView, PromoCheckView,
    StarsUsageView, SubscriptionAutoRenewView,
)
from api.views.crypto import CryptoConfigView, CryptoTopupView, CryptoStatusView
from api.views.embeddings import EmbeddingsView
from api.views.audio import AudioTranscriptionsView, AudioSpeechView
from api.views.batch import BatchListCreateView, BatchDetailView, BatchResultsView, BatchCancelView
from api.views.webhooks import WebhookListCreateView, WebhookDetailView, WebhookTestView
from api.views.audit import AuditLogListView
from api.views.sandboxes import (
    SandboxListCreateView, SandboxDetailView, SandboxExecView,
    SandboxFilesView, SandboxLogsView, SandboxLogsStreamView, SandboxTimeoutView,
)
from api.views.api_status import APIStatusView
from api.views.legal import LegalPrivacyView, LegalTermsView
from api.views.referral import ReferralView, ReferralWithdrawView
from api.views.files import UserFilesView, UserFileDeleteView, GenerationRerunView, GenerationUpscaleView, GenerationVariationsView, GenerationDescribeView, GenerationFavoriteToggleView, FavoritesListView, RemoveBackgroundView
from api.views.generations import GenerationProgressView
from api.views.share import (
    GalleryView, PublicGenerationView, GenerationShareView, GenerationUnshareView, GenerationLikeView,
)
from api.views.compare import CompareView
from api.views.prompts import PromptListCreateView, PromptDetailView
from api.views.projects import ProjectListCreateView, ProjectDetailView, ProjectPublishView, ProjectPublicView, ProjectAuditView
from api.views.collaborators import CollaboratorListCreateView, CollaboratorDetailView
from api.views.project_files import (
    ProjectFileListCreateView, ProjectFileDetailView, ProjectFileSearchView,
    FileVersionListView, FileRestoreView,
)
from api.views.connectors import (
    ConnectorListCreateView, ConnectorDetailView,
    ConnectorReadFilesView, ConnectorFileContentView,
    CommitListCreateView, CommitConfirmView, CommitDeleteView,
    ConnectorSyncView, ConnectorWebhookView,
    ConnectorDeployView,
)
from api.views.deploy import InternalDeployView
from api.views.usage_events import UsageEventListView, UsageEventSummaryView
from api.views.bot_payment import BotPayUrlView
from api.views.ab_tests import ABTestListCreateView, ABTestResultsView
from api.views.telegram_link import TelegramLinkTokenView
from api.views.telegram_webapp import (
    telegram_webapp_auth, telegram_webapp_files, telegram_prepare_share,
)
from api.views.memory import (
    MemoryListCreateView, MemoryDetailView,
    MemoryClearView, MemorySummariesView, MemorySettingsView,
    QuickSaveFactView, MemoryToastView, OrgMemoryView,
)
from api.views.branch import BranchChatView
from api.views.kb_stats import ProjectKBStatsView, ProjectFileReindexView, ProjectFileChunksView
from api.views.deep_research import (
    DeepResearchStartView, DeepResearchStatusView, DeepResearchSaveView,
)
from api.views.personas import PersonaListCreateView, PersonaDetailView
from api.views.arena import ArenaVoteView, ArenaLeaderboardView
from api.views.knowledge_graph import KnowledgeGraphView
from api.views.branding import BrandingView
from api.views.tasks import AITaskListCreateView, AITaskDetailView, AITaskRunNowView
from api.views.agent import AgentStartView, AgentStatusView

app_name = 'api'

urlpatterns = [
    # ========== OpenAI-совместимые эндпоинты (dev-API) ==========
    path('v1/chat/completions', ChatCompletionsView.as_view(), name='chat_completions'),
    path('v1/messages', AnthropicMessagesView.as_view(), name='anthropic_messages'),
    path('v1/models', ModelsListView.as_view(), name='models_list'),
    path('v1/images/generations', ImageGenerationsView.as_view(), name='image_generations'),
    path('v1/images/enhance-prompt/', ImagePromptEnhanceView.as_view(), name='image_enhance_prompt'),
    path('v1/images/compare/', ImageCompareView.as_view(), name='image_compare'),

    # ========== Управление API-ключами ==========
    path('v1/keys/', APIKeyListCreateView.as_view(), name='keys_list_create'),
    path('v1/keys/<int:pk>/', APIKeyDeleteView.as_view(), name='key_delete'),

    # ========== Публичный каталог нейросетей ==========
    path('v1/catalog/categories/', CategoryListView.as_view(), name='catalog_categories'),
    path('v1/catalog/networks/', NetworkListView.as_view(), name='catalog_networks'),
    path('v1/catalog/networks/<slug:slug>/', NetworkDetailView.as_view(), name='catalog_network_detail'),

    # ========== Чаты и сообщения (Next.js web-чат) ==========
    path('v1/chats/', ChatListCreateView.as_view(), name='chats_list_create'),
    path('v1/chats/search/', ChatSearchView.as_view(), name='chats_search'),
    path('v1/chats/<int:pk>/', ChatDetailView.as_view(), name='chat_detail'),
    path('v1/chats/<int:pk>/export/', ChatExportView.as_view(), name='chat_export'),
    path('v1/chats/<int:chat_id>/messages/', SendMessageView.as_view(), name='chat_send_message'),
    path('v1/chats/<int:chat_id>/messages/stream/', StreamMessageView.as_view(), name='chat_stream_message'),
    path('v1/chats/<int:chat_id>/regenerate/', RegenerateView.as_view(), name='chat_regenerate'),
    path('v1/chats/<int:chat_id>/branch/', BranchChatView.as_view(), name='chat_branch'),
    path('v1/chats/<int:chat_id>/research/', DeepResearchStartView.as_view(), name='deep_research_start'),
    path('v1/research/<int:research_id>/', DeepResearchStatusView.as_view(), name='deep_research_status'),
    path('v1/research/<int:research_id>/save/', DeepResearchSaveView.as_view(), name='deep_research_save'),
    path('v1/chats/<int:chat_id>/upload/', ChatFileUploadView.as_view(), name='chat_file_upload'),
    path('v1/uploads/reference-image/', ReferenceImageUploadView.as_view(), name='reference_image_upload'),
    path('v1/messages/<int:message_id>/status/', MessageStatusView.as_view(), name='message_status'),

    # ========== Аутентификация (сессионная) ==========
    path('v1/auth/me/', MeView.as_view(), name='auth_me'),
    path('v1/auth/login/', LoginView.as_view(), name='auth_login'),
    path('v1/auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('v1/auth/register/', RegisterView.as_view(), name='auth_register'),
    path('v1/auth/verify-email/', VerifyEmailView.as_view(), name='auth_verify_email'),
    path('v1/auth/resend-verification/', ResendVerificationView.as_view(), name='auth_resend_verification'),

    # ========== Организации и B2B ==========
    path('v1/orgs/', OrgListCreateView.as_view(), name='org_list_create'),
    path('v1/orgs/<int:org_id>/', OrgDetailView.as_view(), name='org_detail'),
    path('v1/orgs/<int:org_id>/members/', OrgMemberListView.as_view(), name='org_members'),
    path('v1/orgs/<int:org_id>/members/<int:user_id>/', OrgMemberDeleteView.as_view(), name='org_member_delete'),
    path('v1/orgs/<int:org_id>/invites/', OrgInviteListCreateView.as_view(), name='org_invites'),
    path('v1/orgs/<int:org_id>/invoices/', InvoiceListCreateView.as_view(), name='org_invoices'),
    path('v1/orgs/invites/<str:token>/accept/', InviteAcceptView.as_view(), name='invite_accept'),
    path('v1/orgs/<int:org_id>/memory/', OrgMemoryView.as_view(), name='org_memory'),
    path('v1/orgs/<int:pk>/tg-token/', OrgTgTokenView.as_view(), name='org_tg_token'),
    path('v1/orgs/<int:pk>/tg-groups/', OrgTgGroupsView.as_view(), name='org_tg_groups'),

    # ========== Статистика использования ==========
    path('v1/usage/', UsageStatsView.as_view(), name='usage_stats'),

    # ========== Блог (публичный) ==========
    path('v1/blog/categories/', BlogCategoryListView.as_view(), name='blog_categories'),
    path('v1/blog/posts/', BlogPostListView.as_view(), name='blog_posts'),
    path('v1/blog/posts/<slug:slug>/', BlogPostDetailView.as_view(), name='blog_post_detail'),

    # ========== Billing (Phase 3) ==========
    path('v1/billing/tariffs/', TariffListView.as_view(), name='billing_tariffs'),
    path('v1/billing/tariffs/<int:tariff_id>/pay/', TariffPayView.as_view(), name='billing_tariff_pay'),
    path('v1/billing/pages/', PageSaleSettingsView.as_view(), name='billing_pages_settings'),
    path('v1/billing/pages/buy/', BuyPagesView.as_view(), name='billing_buy_pages'),
    path('v1/billing/history/', PaymentHistoryView.as_view(), name='billing_history'),
    path('v1/billing/promo/', ApplyPromoView.as_view(), name='billing_promo'),
    path('v1/billing/promo/check/', PromoCheckView.as_view(), name='billing_promo_check'),
    path('v1/billing/stars-usage/', StarsUsageView.as_view(), name='billing_stars_usage'),
    path('v1/billing/subscription/', SubscriptionAutoRenewView.as_view(), name='billing_subscription'),
    path('v1/billing/crypto/', CryptoConfigView.as_view(), name='billing_crypto_config'),
    path('v1/billing/crypto/topup/', CryptoTopupView.as_view(), name='billing_crypto_topup'),
    path('v1/billing/crypto/status/<int:payment_id>/', CryptoStatusView.as_view(), name='billing_crypto_status'),

    # ========== Phase 6: Advanced API ==========
    path('v1/embeddings', EmbeddingsView.as_view(), name='embeddings'),
    path('v1/audio/transcriptions', AudioTranscriptionsView.as_view(), name='audio_transcriptions'),
    path('v1/audio/speech', AudioSpeechView.as_view(), name='audio_speech'),
    path('v1/batches/', BatchListCreateView.as_view(), name='batch_list_create'),
    path('v1/batches/<int:pk>/', BatchDetailView.as_view(), name='batch_detail'),
    path('v1/batches/<int:pk>/results/', BatchResultsView.as_view(), name='batch_results'),
    path('v1/batches/<int:pk>/cancel/', BatchCancelView.as_view(), name='batch_cancel'),
    path('v1/webhooks/', WebhookListCreateView.as_view(), name='webhook_list_create'),
    path('v1/webhooks/<int:pk>/', WebhookDetailView.as_view(), name='webhook_detail'),
    path('v1/webhooks/<int:pk>/test/', WebhookTestView.as_view(), name='webhook_test'),
    path('v1/audit/', AuditLogListView.as_view(), name='audit_log'),
    path('v1/status/', APIStatusView.as_view(), name='api_status'),

    # ========== Sandbox API (SANDBOX_API_PLAN.md) ==========
    path('v1/sandboxes/', SandboxListCreateView.as_view(), name='sandbox_list_create'),
    path('v1/sandboxes/<str:sandbox_id>/', SandboxDetailView.as_view(), name='sandbox_detail'),
    path('v1/sandboxes/<str:sandbox_id>/exec/', SandboxExecView.as_view(), name='sandbox_exec'),
    path('v1/sandboxes/<str:sandbox_id>/files/', SandboxFilesView.as_view(), name='sandbox_files'),
    path('v1/sandboxes/<str:sandbox_id>/logs/', SandboxLogsView.as_view(), name='sandbox_logs'),
    path('v1/sandboxes/<str:sandbox_id>/logs/stream/', SandboxLogsStreamView.as_view(), name='sandbox_logs_stream'),
    path('v1/sandboxes/<str:sandbox_id>/timeout/', SandboxTimeoutView.as_view(), name='sandbox_timeout'),

    # ========== Юридические документы ==========
    path('v1/legal/privacy/', LegalPrivacyView.as_view(), name='legal_privacy'),
    path('v1/legal/terms/', LegalTermsView.as_view(), name='legal_terms'),

    # ========== Реферальная программа ==========
    path('v1/referral/', ReferralView.as_view(), name='referral'),
    path('v1/referral/withdraw/', ReferralWithdrawView.as_view(), name='referral_withdraw'),

    # ========== Файлы пользователя ==========
    path('v1/files/', UserFilesView.as_view(), name='user_files'),
    path('v1/files/<int:file_id>/', UserFileDeleteView.as_view(), name='user_file_delete'),

    # ========== Прогресс генерации медиа (SSE) ==========
    path('v1/generations/<int:pk>/progress/', GenerationProgressView.as_view(), name='generation_progress'),
    path('v1/generations/<int:pk>/rerun/', GenerationRerunView.as_view(), name='generation_rerun'),
    path('v1/generations/<int:pk>/upscale/', GenerationUpscaleView.as_view(), name='generation_upscale'),
    path('v1/generations/<int:pk>/variations/', GenerationVariationsView.as_view(), name='generation_variations'),
    path('v1/generations/<int:pk>/describe/', GenerationDescribeView.as_view(), name='generation_describe'),
    path('v1/generations/<int:pk>/favorite/', GenerationFavoriteToggleView.as_view(), name='generation_favorite'),
    path('v1/generations/<int:pk>/remove-background/', RemoveBackgroundView.as_view(), name='generation_remove_bg'),
    path('v1/favorites/', FavoritesListView.as_view(), name='favorites_list'),
    path('v1/generations/<int:pk>/share/', GenerationShareView.as_view(), name='generation_share'),
    path('v1/generations/<int:pk>/unshare/', GenerationUnshareView.as_view(), name='generation_unshare'),
    path('v1/generations/<int:pk>/like/', GenerationLikeView.as_view(), name='generation_like'),
    path('v1/generations/<str:slug>/public/', PublicGenerationView.as_view(), name='generation_public'),

    # ========== Публичная галерея (Sprint 7) ==========
    path('v1/gallery/', GalleryView.as_view(), name='gallery'),

    # ========== White-label брендинг ==========
    path('v1/branding/', BrandingView.as_view(), name='branding'),

    # ========== Model Arena (сравнение + Elo-рейтинг) ==========
    path('v1/compare/', CompareView.as_view(), name='compare'),
    path('v1/arena/vote/', ArenaVoteView.as_view(), name='arena_vote'),
    path('v1/arena/leaderboard/', ArenaLeaderboardView.as_view(), name='arena_leaderboard'),

    # ========== Промпт-библиотека ==========
    path('v1/prompts/', PromptListCreateView.as_view(), name='prompts_list_create'),
    path('v1/prompts/<int:pk>/', PromptDetailView.as_view(), name='prompt_detail'),

    # ========== Проекты (папки чатов) ==========
    path('v1/projects/', ProjectListCreateView.as_view(), name='projects_list_create'),
    path('v1/projects/<int:pk>/', ProjectDetailView.as_view(), name='project_detail'),
    path('v1/projects/<int:pk>/publish/', ProjectPublishView.as_view(), name='project_publish'),
    path('v1/public/spaces/<str:slug>/', ProjectPublicView.as_view(), name='project_public'),
    path('v1/projects/<int:pk>/files/', ProjectFileListCreateView.as_view(), name='project_files'),
    path('v1/projects/<int:pk>/files/search/', ProjectFileSearchView.as_view(), name='project_files_search'),
    path('v1/projects/<int:pk>/files/<int:file_id>/', ProjectFileDetailView.as_view(), name='project_file_detail'),
    path('v1/projects/<int:pk>/files/<int:file_id>/versions/', FileVersionListView.as_view(), name='project_file_versions'),
    path('v1/projects/<int:pk>/files/<int:file_id>/reindex/', ProjectFileReindexView.as_view(), name='project_file_reindex'),
    path('v1/projects/<int:pk>/files/<int:file_id>/chunks/', ProjectFileChunksView.as_view(), name='project_file_chunks'),
    path('v1/projects/<int:pk>/kb/stats/', ProjectKBStatsView.as_view(), name='project_kb_stats'),
    path('v1/projects/<int:pk>/files/<int:file_id>/versions/<int:version_id>/restore/', FileRestoreView.as_view(), name='project_file_restore'),
    path('v1/projects/<int:pk>/collaborators/', CollaboratorListCreateView.as_view(), name='project_collaborators'),
    path('v1/projects/<int:pk>/collaborators/<int:cid>/', CollaboratorDetailView.as_view(), name='project_collaborator_detail'),
    path('v1/projects/<int:pk>/audit/', ProjectAuditView.as_view(), name='project_audit'),
    path('v1/projects/<int:pk>/graph/', KnowledgeGraphView.as_view(), name='project_graph'),
    path('v1/projects/<int:pk>/connectors/', ConnectorListCreateView.as_view(), name='project_connectors'),
    path('v1/projects/<int:pk>/connectors/<int:connector_id>/', ConnectorDetailView.as_view(), name='project_connector_detail'),
    path('v1/projects/<int:pk>/connectors/<int:connector_id>/files/', ConnectorReadFilesView.as_view(), name='connector_files'),
    path('v1/projects/<int:pk>/connectors/<int:connector_id>/file/', ConnectorFileContentView.as_view(), name='connector_file_content'),
    path('v1/projects/<int:pk>/commits/', CommitListCreateView.as_view(), name='project_commits'),
    path('v1/projects/<int:pk>/commits/<int:commit_id>/confirm/', CommitConfirmView.as_view(), name='commit_confirm'),
    path('v1/projects/<int:pk>/commits/<int:commit_id>/', CommitDeleteView.as_view(), name='commit_detail'),
    path('v1/projects/<int:pk>/connectors/<int:connector_id>/sync/', ConnectorSyncView.as_view(), name='connector_sync'),
    path('v1/projects/<int:pk>/connectors/<int:connector_id>/webhook/', ConnectorWebhookView.as_view(), name='connector_webhook'),
    path('v1/projects/<int:pk>/connectors/<int:connector_id>/deploy/', ConnectorDeployView.as_view(), name='connector_deploy'),
    path('v1/internal/deploy/', InternalDeployView.as_view(), name='internal_deploy'),

    # ========== Unified Usage Events (admin analytics) ==========
    path('v1/usage-events/', UsageEventListView.as_view(), name='usage_events'),
    path('v1/usage-events/summary/', UsageEventSummaryView.as_view(), name='usage_events_summary'),

    # ========== Bot Robokassa Payment ==========
    path('v1/billing/bot-pay-url/', BotPayUrlView.as_view(), name='bot_pay_url'),

    # ========== A/B Prompt Tests (admin) ==========
    path('v1/ab-tests/', ABTestListCreateView.as_view(), name='ab_test_list'),
    path('v1/ab-tests/<int:pk>/results/', ABTestResultsView.as_view(), name='ab_test_results'),

    # ========== STUDIO (Vibe-Coding Studio) ==========
    path('v1/studio/', include('studio.urls')),

    # ========== Persistent Memory ==========
    path('v1/memory/', MemoryListCreateView.as_view(), name='memory_list_create'),
    path('v1/memory/<int:pk>/', MemoryDetailView.as_view(), name='memory_detail'),
    path('v1/memory/clear/', MemoryClearView.as_view(), name='memory_clear'),
    path('v1/memory/summaries/', MemorySummariesView.as_view(), name='memory_summaries'),
    path('v1/memory/settings/', MemorySettingsView.as_view(), name='memory_settings'),
    path('v1/memory/quick-save/', QuickSaveFactView.as_view(), name='memory_quick_save'),
    path('v1/memory/toast/', MemoryToastView.as_view(), name='memory_toast'),

    # ========== AI Personas ==========
    path('v1/personas/', PersonaListCreateView.as_view(), name='persona_list_create'),
    path('v1/personas/<int:persona_id>/', PersonaDetailView.as_view(), name='persona_detail'),

    # ========== Agent Mode на вебе (U4) ==========
    path('v1/agent/', AgentStartView.as_view(), name='agent_start'),
    path('v1/agent/<int:run_id>/', AgentStatusView.as_view(), name='agent_status'),

    # ========== AI-задачи по расписанию (S2, общие для веба и бота) ==========
    path('v1/tasks/', AITaskListCreateView.as_view(), name='ai_tasks'),
    path('v1/tasks/<int:pk>/', AITaskDetailView.as_view(), name='ai_task_detail'),
    path('v1/tasks/<int:pk>/run/', AITaskRunNowView.as_view(), name='ai_task_run'),

    # ========== Telegram Bot ==========
    path('v1/telegram/link-token/', TelegramLinkTokenView.as_view(), name='telegram_link_token'),
    path('v1/telegram/webapp-auth/', telegram_webapp_auth, name='telegram-webapp-auth'),
    path('v1/telegram/webapp/files/', telegram_webapp_files, name='telegram-webapp-files'),
    path('v1/telegram/webapp/prepare-share/', telegram_prepare_share, name='telegram-prepare-share'),

    # ========== OpenAPI / Swagger ==========
    path('v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('v1/docs/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='swagger_ui'),
    path('v1/redoc/', SpectacularRedocView.as_view(url_name='api:schema'), name='redoc'),
]
