from django.urls import path
from . import views

app_name = 'aitext'

urlpatterns = [
    path('api/networks/', views.get_networks_by_category, name='networks_api'),
    path('api/create-chat/', views.create_chat, name='create_chat'),
    path('api/send/<int:chat_id>/', views.send_message, name='send_message'),
    path('api/message_status/<int:message_id>/', views.message_status, name='message_status'),
    path('api/delete-chat/<int:chat_id>/', views.delete_chat, name='delete_chat'),
    path('api/user-chats/', views.user_chats, name='user_chats'),
    path('api/chat-settings/<int:chat_id>/', views.save_chat_settings, name='save_chat_settings'),
    path('api/network-config/<slug:slug>/', views.get_network_config_api, name='network_config_api'),

    path('api/user-files/', views.user_files_api, name='user_files_api'),
    path('api/delete-file/<str:file_id>/', views.delete_file, name='delete_file'),
]