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
)
from api.views.auth import MeView, LoginView, LogoutView, RegisterView

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
    path('v1/messages/<int:message_id>/status/', MessageStatusView.as_view(), name='message_status'),

    # ========== Аутентификация (сессионная) ==========
    path('v1/auth/me/', MeView.as_view(), name='auth_me'),
    path('v1/auth/login/', LoginView.as_view(), name='auth_login'),
    path('v1/auth/logout/', LogoutView.as_view(), name='auth_logout'),
    path('v1/auth/register/', RegisterView.as_view(), name='auth_register'),

    # ========== OpenAPI / Swagger ==========
    path('v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('v1/docs/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='swagger_ui'),
    path('v1/redoc/', SpectacularRedocView.as_view(url_name='api:schema'), name='redoc'),
]
