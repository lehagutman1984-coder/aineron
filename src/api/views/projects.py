from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework import serializers

from aitext.models import Project, ProjectFile


class ProjectSerializer(serializers.ModelSerializer):
    chat_count = serializers.SerializerMethodField()
    file_count = serializers.SerializerMethodField()

    class Meta:
        model = Project
        fields = [
            'id', 'name', 'system_prompt', 'color', 'icon',
            'chat_count', 'file_count', 'created_at',
            'is_public', 'public_slug', 'public_show_files', 'public_show_chats',
        ]
        read_only_fields = ['id', 'created_at', 'chat_count', 'file_count', 'public_slug']

    def get_chat_count(self, obj):
        return obj.chats.count()

    def get_file_count(self, obj):
        return obj.knowledge_files.filter(status='ready', enabled=True).count()


class ProjectListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        projects = Project.objects.filter(user=request.user).prefetch_related('chats', 'knowledge_files')
        return Response(ProjectSerializer(projects, many=True).data)

    def post(self, request):
        ser = ProjectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        project = ser.save(user=request.user)
        return Response(ProjectSerializer(project).data, status=201)


class ProjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        ser = ProjectSerializer(project, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save()
        return Response(ProjectSerializer(project).data)

    def delete(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        project.delete()
        return Response(status=204)


class ProjectPublishView(APIView):
    """POST /api/v1/projects/<pk>/publish/ — toggle публичности Space."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        is_public = request.data.get('is_public')
        if is_public is None:
            is_public = not project.is_public
        else:
            is_public = bool(is_public)

        project.is_public = is_public
        project.public_show_files = bool(request.data.get('public_show_files', project.public_show_files))
        project.public_show_chats = bool(request.data.get('public_show_chats', project.public_show_chats))
        project.save()
        return Response(ProjectSerializer(project).data)


class PublicSpaceFileSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProjectFile
        fields = ['id', 'filename', 'file_size', 'file_type', 'created_at']


class ProjectPublicView(APIView):
    """GET /api/v1/public/spaces/<slug>/ — публичная страница Space."""
    permission_classes = [AllowAny]

    def get(self, request, slug):
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

        return Response(data)
