from django.urls import re_path
from aitext import consumers as aitext_consumers

websocket_urlpatterns = [
    re_path(r'ws/yjs/(?P<project_id>\d+)/$', aitext_consumers.YjsConsumer.as_asgi()),
    re_path(r'ws/voice/(?P<chat_id>\d+)/$', aitext_consumers.VoiceConsumer.as_asgi()),
]
