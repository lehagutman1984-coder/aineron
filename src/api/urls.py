from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from api.views.keys import APIKeyListCreateView, APIKeyDeleteView
from api.views.chat import ChatCompletionsView
from api.views.anthropic import AnthropicMessagesView
from api.views.images import ImageGenerationsView
from api.views.models_list import ModelsListView
from api.views.catalog import CategoryListView, NetworkListView, NetworkDetailView
from api.views.chats import (
    ChatListCreateView, ChatDetailView, SendMessageView, MessageStatusView,
    StreamMessageView,
)
from api.views.auth import MeView, LoginView, LogoutView, RegisterView, VerifyEmailView, ResendVerificationView
from api.views.teams import (
    OrgListCreateView, OrgDetailView,
    OrgMemberListView, OrgMemberDeleteView,
    OrgInviteListCreateView, InviteAcceptView,
)
from api.views.invoices import InvoiceListCreateView
from api.views.usage import UsageStatsView
from api.views.blog import BlogCategoryListView, BlogPostListView, BlogPostDetailView
from api.views.billing import (
    TariffListView, TariffPayView, PageSaleSettingsView,
    BuyPagesView, PaymentHistoryView, ApplyPromoView,
)
from api.views.embeddings import EmbeddingsView
from api.views.audio import AudioTranscriptionsView, AudioSpeechView
from api.views.batch import BatchListCreateView, BatchDetailView, BatchResultsView, BatchCancelView
from api.views.webhooks import WebhookListCreateView, WebhookDetailView, WebhookTestView
from api.views.audit import AuditLogListView
from api.views.api_status import APIStatusView
from api.views.legal import LegalPrivacyView, LegalTermsView
from api.views.referral import ReferralView, ReferralWithdrawView
from api.views.files import UserFilesView, UserFileDeleteView

app_name = 'api'

urlpatterns = [
    # ========== OpenAI-совместимые эндпоинты (dev-API) ==========
    path('v1/chat/completions', ChatCompletionsView.as_view(), name='chat_completions'),
    path('v1/messages', AnthropicMessagesView.as_view(), name='anthropic_messages'),
    path('v1/models', ModelsListView.as_view(), name='models_list'),
    path('v1/images/generations', ImageGenerationsView.as_view(), name='image_generations'),

    # ========== Управление API-ключами ==========
    path('v1/keys/', APIKeyListCreateView.as_view(), name='keys_list_create'),
    path('v1/keys/<int:pk>/', APIKeyDeleteView.as_view(), name='key_delete'),

    # ========== Публичный каталог нейросетей ==========
    path('v1/catalog/categories/', CategoryListView.as_view(), name='catalog_categories'),
    path('v1/catalog/networks/', NetworkListView.as_view(), name='catalog_networks'),
    path('v1/catalog/networks/<slug:slug>/', NetworkDetailView.as_view(), name='catalog_network_detail'),

    # ========== Чаты и сообщения (Next.js web-чат) ==========
    path('v1/chats/', ChatListCreateView.as_view(), name='chats_list_create'),
    path('v1/chats/<int:pk>/', ChatDetailView.as_view(), name='chat_detail'),
    path('v1/chats/<int:chat_id>/messages/', SendMessageView.as_view(), name='chat_send_message'),
    path('v1/chats/<int:chat_id>/messages/stream/', StreamMessageView.as_view(), name='chat_stream_message'),
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

    # ========== Юридические документы ==========
    path('v1/legal/privacy/', LegalPrivacyView.as_view(), name='legal_privacy'),
    path('v1/legal/terms/', LegalTermsView.as_view(), name='legal_terms'),

    # ========== Реферальная программа ==========
    path('v1/referral/', ReferralView.as_view(), name='referral'),
    path('v1/referral/withdraw/', ReferralWithdrawView.as_view(), name='referral_withdraw'),

    # ========== Файлы пользователя ==========
    path('v1/files/', UserFilesView.as_view(), name='user_files'),
    path('v1/files/<int:file_id>/', UserFileDeleteView.as_view(), name='user_file_delete'),

    # ========== OpenAPI / Swagger ==========
    path('v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('v1/docs/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='swagger_ui'),
    path('v1/redoc/', SpectacularRedocView.as_view(url_name='api:schema'), name='redoc'),
]
