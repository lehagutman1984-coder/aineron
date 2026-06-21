from rest_framework import serializers
from aitext.models import Chat, Message
from api.serializers.catalog import NeuralNetworkListSerializer


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            'id', 'role', 'content', 'plain_text', 'files', 'status',
            'error_message', 'search_context', 'created_at',
        ]


class NeuralNetworkChatSerializer(NeuralNetworkListSerializer):
    """Расширенный сериализатор для chat detail — включает config_json для рендеринга настроек."""

    class Meta(NeuralNetworkListSerializer.Meta):
        fields = NeuralNetworkListSerializer.Meta.fields + ['config_json']


class ChatListSerializer(serializers.ModelSerializer):
    network = NeuralNetworkListSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = ['id', 'title', 'network', 'project_id', 'last_message', 'created_at', 'updated_at']

    def get_last_message(self, obj):
        msg = obj.messages.order_by('-created_at').first()
        if not msg:
            return None
        return {
            'role': msg.role,
            'preview': msg.plain_text[:80] if msg.plain_text else (msg.content[:80] if msg.content else ''),
            'status': msg.status,
        }


class ChatDetailSerializer(serializers.ModelSerializer):
    network = NeuralNetworkChatSerializer(read_only=True)
    messages = MessageSerializer(many=True, read_only=True)
    project = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = ['id', 'title', 'network', 'project_id', 'project', 'messages', 'settings', 'created_at', 'updated_at']

    def get_project(self, obj):
        p = obj.project
        if not p:
            return None
        return {
            'id': p.id,
            'name': p.name,
            'system_prompt': p.system_prompt,
            'color': p.color,
            'icon': p.icon,
        }


class ChatUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Chat
        fields = ['title']


class SendMessageSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, default='')
    files = serializers.ListField(
        child=serializers.DictField(), required=False, default=list
    )
    settings = serializers.DictField(required=False, default=dict)
    attachment_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list
    )
    web_search = serializers.BooleanField(required=False, default=False)
