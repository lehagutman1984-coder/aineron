import re
from rest_framework import serializers
from aitext.models import UserMemory, ChatSummary


class UserMemorySerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)

    class Meta:
        model = UserMemory
        fields = [
            'id', 'category', 'category_display', 'content',
            'source', 'is_active', 'is_pinned',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'source', 'created_at', 'updated_at', 'category_display']

    def create(self, validated_data):
        content = validated_data.get('content', '')
        validated_data['source'] = 'user'
        validated_data['content_key'] = re.sub(r'[^а-яёa-z0-9]', '', content.lower())[:255]
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ChatSummarySerializer(serializers.ModelSerializer):
    chat_title = serializers.CharField(source='chat.title', read_only=True)
    network_name = serializers.CharField(source='chat.network.name', read_only=True)

    class Meta:
        model = ChatSummary
        fields = [
            'id', 'chat_id', 'chat_title', 'network_name',
            'summary_text', 'message_count', 'created_at', 'updated_at',
        ]
        read_only_fields = fields
