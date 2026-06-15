from rest_framework import serializers
from .models import StudioProject, StudioFile, StudioPipelineState, StudioVersion


class StudioProjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioProject
        fields = '__all__'
        read_only_fields = (
            'id', 'user', 'status',
            'sandbox_container_id', 'preview_port', 'repo_url',
            'stars_reserved', 'stars_spent', 'created_at', 'updated_at',
        )


class StudioProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioProject
        fields = ('id', 'name', 'description', 'mode', 'entry_mode', 'target_url', 'target_stack',
                  'status', 'created_at')
        read_only_fields = ('id', 'status', 'created_at')


class StudioFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioFile
        fields = ('id', 'path', 'language', 'last_modified_by', 'updated_at')


class StudioFileDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioFile
        fields = ('id', 'path', 'content', 'language', 'last_modified_by', 'updated_at')


class PipelineStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioPipelineState
        fields = '__all__'


class StudioVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioVersion
        fields = '__all__'
