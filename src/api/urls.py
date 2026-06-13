from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from api.views.keys import APIKeyListCreateView, APIKeyDeleteView
from api.views.chat import ChatCompletionsView
from api.views.anthropic import AnthropicMessagesView
from api.views.images import ImageGenerationsView
from api.views.models_list import ModelsListView

app_name = 'api'

urlpatterns = [
    # ========== OpenAI-совместимые эндпоинты ==========
    path('v1/chat/completions', ChatCompletionsView.as_view(), name='chat_completions'),
    path('v1/messages', AnthropicMessagesView.as_view(), name='anthropic_messages'),
    path('v1/models', ModelsListView.as_view(), name='models_list'),
    path('v1/images/generations', ImageGenerationsView.as_view(), name='image_generations'),

    # ========== Управление API-ключами ==========
    path('v1/keys/', APIKeyListCreateView.as_view(), name='keys_list_create'),
    path('v1/keys/<int:pk>/', APIKeyDeleteView.as_view(), name='key_delete'),

    # ========== OpenAPI / Swagger ==========
    path('v1/schema/', SpectacularAPIView.as_view(), name='schema'),
    path('v1/docs/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='swagger_ui'),
    path('v1/redoc/', SpectacularRedocView.as_view(url_name='api:schema'), name='redoc'),
]
