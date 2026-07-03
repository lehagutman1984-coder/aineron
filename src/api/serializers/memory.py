from rest_framework import serializers
from aitext.models import UserMemory, ChatSummary
from aitext.memory import normalize_fact


class UserMemorySerializer(serializers.ModelSerializer):
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    # U1: скоуп памяти — проект (записываемый) и организация (read-only;
    # орг-факты создаются через /orgs/<id>/memory/)
    project_name = serializers.CharField(source='project.name', read_only=True, default=None)
    organization_name = serializers.CharField(source='organization.name', read_only=True, default=None)

    class Meta:
        model = UserMemory
        fields = [
            'id', 'category', 'category_display', 'content',
            'source', 'is_active', 'is_pinned',
            'project', 'project_name', 'organization', 'organization_name',
            'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'source', 'organization', 'organization_name',
                            'project_name', 'created_at', 'updated_at', 'category_display']

    def validate_project(self, value):
        if value is not None and value.user_id != self.context['request'].user.id:
            raise serializers.ValidationError('Проект не принадлежит пользователю')
        return value

    def create(self, validated_data):
        content = validated_data.get('content', '')
        validated_data['source'] = 'user'
        validated_data['content_key'] = normalize_fact(content)  # B3: единая нормализация
        validated_data['user'] = self.context['request'].user
        return super().create(validated_data)


class ChatSummarySerializer(serializers.ModelSerializer):
    chat_title = serializers.CharField(source='chat.title', read_only=True)
    network_name = serializers.CharField(source='chat.network.name', read_only=True)
    best_summary = serializers.SerializerMethodField()

    class Meta:
        model = ChatSummary
        fields = [
            'id', 'chat_id', 'chat_title', 'network_name',
            'summary_text', 'rolling_summary', 'best_summary',
            'message_count', 'last_compressed_message_id',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_best_summary(self, obj):
        return (obj.summary_text or obj.rolling_summary or '').strip()
