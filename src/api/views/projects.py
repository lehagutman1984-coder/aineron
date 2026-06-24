from django.db import models
from django.shortcuts import get_object_or_404
from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import serializers

from aitext.models import Project, ProjectFile, ProjectCollaborator
from api.throttling import PublicSpaceThrottle
from api.views._project_access import get_project_for_user, get_project_owner_only, user_role_for_project


class ProjectSerializer(serializers.ModelSerializer):
    chat_count = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'system_prompt', 'color', 'icon', 'status',
            'chat_count', 'file_count', 'created_at',
            'is_public', 'public_slug', 'public_show_files', 'public_show_chats',
            'public_views', 'user_role',
        ]
        read_only_fields = ['id', 'created_at', 'chat_count', 'file_count', 'public_slug', 'public_views', 'user_role']

    def get_chat_count(self, obj):
        return obj.chats.count()

    def get_file_count(self, obj):
        return obj.knowledge_files.filter(status='ready', enabled=True).count()

    def get_user_role(self, obj):
        request = self.context.get('request')
        if request is None:
            return 'owner'
        return user_role_for_project(obj, request.user)


class ProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        owned = Project.objects.filter(user=request.user).prefetch_related('chats', 'knowledge_files')
        collab_ids = ProjectCollaborator.objects.filter(
            user=request.user
        ).values_list('project_id', flat=True)
        shared = Project.objects.filter(
            pk__in=collab_ids
        ).prefetch_related('chats', 'knowledge_files')

        all_projects = list(owned) + [p for p in shared if p.user_id != request.user.pk]
        all_projects.sort(key=lambda p: p.created_at, reverse=True)
        return Response(ProjectSerializer(all_projects, many=True, context={'request': request}).data)

    def post(self, request):
        ser = ProjectSerializer(data=request.data, context={'request': request})
        ser.is_valid(raise_exception=True)
        project = ser.save(user=request.user)
        return Response(ProjectSerializer(project, context={'request': request}).data, status=201)


class ProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = get_project_for_user(pk, request.user, write=False)
        return Response(ProjectSerializer(project, context={'request': request}).data)

    def patch(self, request, pk):
        project = get_project_for_user(pk, request.user, write=True)
        ser = ProjectSerializer(project, data=request.data, partial=True, context={'request': request})
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ProjectSerializer(project, context={'request': request}).data)

    def delete(self, request, pk):
        project = get_project_owner_only(pk, request.user)
        project.delete()
        return Response(status=204)


class ProjectPublishView(APIView):
    """POST /api/v1/projects/<pk>/publish/ — toggle публичности Space."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        project = get_project_owner_only(pk, request.user)
        is_public = request.data.get('is_public')
        if is_public is None:
            is_public = not project.is_public
        else:
            is_public = bool(is_public)

        project.is_public = is_public
        project.public_show_files = bool(request.data.get('public_show_files', project.public_show_files))
        project.public_show_chats = bool(request.data.get('public_show_chats', project.public_show_chats))
        project.save()
        from aitext.tasks import _write_audit
        _write_audit(project, request.user, 'published' if is_public else 'unpublished')
        return Response(ProjectSerializer(project, context={'request': request}).data)


class PublicSpaceFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = ['id', 'filename', 'file_size', 'file_type', 'created_at']


class ProjectPublicView(APIView):
    """GET /api/v1/public/spaces/<slug>/ — публичная страница Space."""
    permission_classes = [AllowAny]
    throttle_classes = [PublicSpaceThrottle]

    _CACHE_TTL = 60  # секунд

    def get(self, request, slug):
        cache_key = f'public_space:{slug}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)

        project = get_object_or_404(Project, public_slug=slug, is_public=True)

        data = {
            'id': project.id,
            'name': project.name,
            'system_prompt': project.system_prompt,
            'icon': project.icon,
            'color': project.color,
            'created_at': project.created_at,
            'public_show_files': project.public_show_files,
            'public_show_chats': project.public_show_chats,
        }

        if project.public_show_files:
            files = project.knowledge_files.filter(status='ready', enabled=True)
            data['files'] = PublicSpaceFileSerializer(files, many=True).data
        else:
            data['files'] = []

        if project.public_show_chats:
            chats = project.chats.order_by('-updated_at')[:10]
            data['chats'] = [
                {'id': c.id, 'title': c.title, 'updated_at': c.updated_at}
                for c in chats
            ]
        else:
            data['chats'] = []

        # Sprint 5.5: track public_views asynchronously (non-blocking)
        try:
            from django.conf import settings as djsettings
            if getattr(djsettings, 'PROJECT_PUBLIC_HARDENING', False):
                Project.objects.filter(pk=project.pk).update(public_views=models.F('public_views') + 1)
        except Exception:
            pass

        cache.set(cache_key, data, self._CACHE_TTL)
        return Response(data)


class ProjectAuditView(APIView):
    """GET /api/v1/projects/<pk>/audit/ — журнал аудита (owner + editors)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from django.conf import settings as djsettings
        if not getattr(djsettings, 'PROJECT_AUDIT_LOG', False):
            return Response({'entries': []})

        from aitext.models import ProjectAuditEntry
        project = get_project_for_user(pk, request.user, write=False)
        qs = ProjectAuditEntry.objects.filter(project=project).select_related('actor')[:100]
        entries = [
            {
                'id': e.id,
                'action': e.action,
                'action_display': e.get_action_display(),
                'target': e.target,
                'files_used': e.files_used,
                'actor_email': e.actor.email if e.actor else None,
                'created_at': e.created_at,
            }
            for e in qs
        ]
        return Response({'entries': entries})
