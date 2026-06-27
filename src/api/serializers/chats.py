from rest_framework import serializers
from aitext.models import Chat, Message
from api.serializers.catalog import NeuralNetworkListSerializer


class MessageSerializer(serializers.ModelSerializer):
    is_research = serializers.SerializerMethodField()
    research_id = serializers.SerializerMethodField()
    used_memory = serializers.SerializerMethodField()

    class Meta:
        model = Message
        fields = [
            'id', 'role', 'content', 'plain_text', 'files', 'status',
            'error_message', 'search_context', 'kb_sources', 'variants', 'created_at',
            'is_research', 'research_id', 'used_memory',
        ]

    def get_is_research(self, obj):
        try:
            return obj.deep_research is not None
        except Exception:
            return False

    def get_research_id(self, obj):
        try:
            dr = obj.deep_research
            return dr.id if dr is not None else None
        except Exception:
            return None

    def get_used_memory(self, obj):
        return bool((obj.settings or {}).get('used_memory', False))


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
    parent_chat_id = serializers.SerializerMethodField()
    branches = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = ['id', 'title', 'network', 'project_id', 'project', 'messages', 'settings', 'created_at', 'updated_at', 'parent_chat_id', 'branches']

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

    def get_parent_chat_id(self, obj):
        return obj.parent_chat_id

    def get_branches(self, obj):
        return list(
            obj.branches.values('id', 'title', 'created_at').order_by('-created_at')[:10]
        )


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
