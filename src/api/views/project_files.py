import os
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

from aitext.models import Project, ProjectFile


MAX_FILE_SIZE = 20 * 1024 * 1024  # 20 MB
MAX_FILES_PER_PROJECT = 20

ALLOWED_EXTENSIONS = {
    '.pdf', '.txt', '.md', '.rst',
    '.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.json', '.yaml', '.yml',
    '.toml', '.ini', '.env', '.sh', '.sql',
    '.doc', '.docx', '.odt', '.rtf',
    '.csv', '.xml',
}


def _detect_file_type(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        return 'pdf'
    if ext in {'.doc', '.docx', '.odt', '.rtf'}:
        return 'doc'
    if ext in {'.txt', '.md', '.rst', '.csv'}:
        return 'text'
    if ext in {'.py', '.js', '.ts', '.tsx', '.jsx', '.html', '.css', '.json', '.yaml', '.yml', '.toml', '.ini', '.sh', '.sql', '.xml'}:
        return 'code'
    return 'other'


class ProjectFileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()

    class Meta:
        model = ProjectFile
        fields = [
            'id', 'filename', 'file_url', 'file_size', 'file_type',
            'status', 'embed_status', 'source', 'enabled', 'created_at',
        ]
        read_only_fields = [
            'id', 'filename', 'file_url', 'file_size', 'file_type',
            'status', 'embed_status', 'source', 'created_at',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None


class ProjectFileListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        files = project.knowledge_files.exclude(source='repo')
        return Response(ProjectFileSerializer(files, many=True, context={'request': request}).data)

    def post(self, request, pk):
        project = get_object_or_404(Project, pk=pk, user=request.user)

        if project.knowledge_files.count() >= MAX_FILES_PER_PROJECT:
            return Response(
                {'error': f'Максимум {MAX_FILES_PER_PROJECT} файлов на проект'},
                status=400,
            )

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': 'Файл не передан'}, status=400)

        if uploaded.size > MAX_FILE_SIZE:
            return Response({'error': 'Файл слишком большой (макс. 20 МБ)'}, status=400)

        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Response({'error': f'Формат {ext} не поддерживается'}, status=400)

        pf = ProjectFile.objects.create(
            project=project,
            filename=uploaded.name,
            file=uploaded,
            file_size=uploaded.size,
            file_type=_detect_file_type(uploaded.name),
            status='processing',
        )

        # Запускаем извлечение текста асинхронно
        from aitext.tasks import process_project_file
        process_project_file.delay(pf.id)

        return Response(
            ProjectFileSerializer(pf, context={'request': request}).data,
            status=201,
        )


class ProjectFileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_file(self, request, pk, file_id):
        project = get_object_or_404(Project, pk=pk, user=request.user)
        return get_object_or_404(ProjectFile, pk=file_id, project=project)

    def patch(self, request, pk, file_id):
        """Переключить enabled."""
        pf = self._get_file(request, pk, file_id)
        enabled = request.data.get('enabled')
        if enabled is not None:
            pf.enabled = bool(enabled)
            pf.save(update_fields=['enabled'])
        return Response(ProjectFileSerializer(pf, context={'request': request}).data)

    def delete(self, request, pk, file_id):
        pf = self._get_file(request, pk, file_id)
        # Удаляем физический файл
        try:
            pf.file.delete(save=False)
        except Exception:
            pass
        pf.delete()
        return Response(status=204)
