from rest_framework import serializers
from aitext.models import Chat, Message
from api.serializers.catalog import NeuralNetworkListSerializer


class MessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = Message
        fields = [
            'id', 'role', 'content', 'plain_text', 'files', 'status',
            'error_message', 'created_at',
        ]


class ChatListSerializer(serializers.ModelSerializer):
    network = NeuralNetworkListSerializer(read_only=True)
    last_message = serializers.SerializerMethodField()

    class Meta:
        model = Chat
        fields = ['id', 'title', 'network', 'last_message', 'created_at', 'updated_at']

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
    network = NeuralNetworkListSerializer(read_only=True)
    messages = MessageSerializer(many=True, read_only=True)

    class Meta:
        model = Chat
        fields = ['id', 'title', 'network', 'messages', 'settings', 'created_at', 'updated_at']


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
