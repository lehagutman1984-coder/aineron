from rest_framework import serializers
from .models import StudioProject, StudioFile, StudioPipelineState, StudioVersion, StudioTemplate


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
    template_slug = serializers.CharField(write_only=True, required=False, allow_blank=True)
    selected_features = serializers.ListField(
        child=serializers.CharField(), required=False, default=list, write_only=True,
    )

    class Meta:
        model = StudioProject
        fields = ('id', 'name', 'description', 'mode', 'entry_mode', 'target_url', 'target_stack',
                  'status', 'created_at', 'template_slug', 'selected_features')
        read_only_fields = ('id', 'status', 'created_at')

    def create(self, validated_data):
        template_slug = validated_data.pop('template_slug', None)
        selected_features = validated_data.pop('selected_features', [])
        project = super().create(validated_data)
        if template_slug:
            from .models import StudioTemplate
            try:
                tmpl = StudioTemplate.objects.get(slug=template_slug, is_public=True)
                if not project.description:
                    project.description = tmpl.seed_prompt[:500]
                    project.save(update_fields=['description'])
                tmpl.usage_count += 1
                tmpl.save(update_fields=['usage_count'])
            except StudioTemplate.DoesNotExist:
                pass
        if selected_features:
            project.interview_data = project.interview_data or {}
            project.interview_data['features'] = selected_features
            project.save(update_fields=['interview_data'])
        return project


class StudioFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioFile
        fields = ('id', 'path', 'language', 'last_modified_by', 'updated_at')


class StudioFileDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioFile
        fields = ('id', 'path', 'content', 'language', 'last_modified_by', 'updated_at')


class PipelineStateSerializer(serializers.ModelSerializer):
    max_iterations = serializers.SerializerMethodField()

    class Meta:
        model = StudioPipelineState
        fields = '__all__'

    def get_max_iterations(self, obj):
        from django.conf import settings
        project_max = obj.project.max_iterations if hasattr(obj, 'project') else 0
        return project_max or getattr(settings, 'STUDIO_MAX_ITERATIONS', 3)


class StudioVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioVersion
        fields = '__all__'


class StudioTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudioTemplate
        fields = '__all__'
