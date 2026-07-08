import os
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import serializers

from aitext.models import Project, ProjectFile
from api.views._project_access import get_project_for_user
from api.error_messages import em


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
    usage_hits = serializers.SerializerMethodField()
    last_used_at = serializers.SerializerMethodField()

    class Meta:
        model = ProjectFile
        fields = [
            'id', 'filename', 'file_url', 'file_size', 'file_type',
            'status', 'embed_status', 'source', 'enabled', 'created_at',
            'usage_hits', 'last_used_at',
        ]
        read_only_fields = [
            'id', 'filename', 'file_url', 'file_size', 'file_type',
            'status', 'embed_status', 'source', 'created_at',
            'usage_hits', 'last_used_at',
        ]

    def get_file_url(self, obj):
        request = self.context.get('request')
        if obj.file and request:
            return request.build_absolute_uri(obj.file.url)
        return None

    def get_usage_hits(self, obj):
        try:
            return obj.usage_stat.hits
        except Exception:
            return 0

    def get_last_used_at(self, obj):
        try:
            return obj.usage_stat.last_used_at
        except Exception:
            return None


class ProjectFileListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = get_project_for_user(pk, request.user, write=False)
        files = project.knowledge_files.exclude(source='repo')
        return Response(ProjectFileSerializer(files, many=True, context={'request': request}).data)

    def post(self, request, pk):
        project = get_project_for_user(pk, request.user, write=True)

        if project.knowledge_files.count() >= MAX_FILES_PER_PROJECT:
            return Response(
                {'error': em('max_files_per_project', max_files=MAX_FILES_PER_PROJECT)},
                status=400,
            )

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'error': em('file_missing')}, status=400)

        if uploaded.size > MAX_FILE_SIZE:
            return Response({'error': em('file_too_large', size_mb=20)}, status=400)

        ext = os.path.splitext(uploaded.name)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            return Response({'error': em('file_format_unsupported', ext=ext)}, status=400)

        pf = ProjectFile.objects.create(
            project=project,
            filename=uploaded.name,
            file=uploaded,
            file_size=uploaded.size,
            file_type=_detect_file_type(uploaded.name),
            status='processing',
        )

        from aitext.tasks import process_project_file, _write_audit
        process_project_file.delay(pf.id)
        _write_audit(project, request.user, 'file_upload', target=uploaded.name)

        return Response(
            ProjectFileSerializer(pf, context={'request': request}).data,
            status=201,
        )


class ProjectFileDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_file(self, request, pk, file_id, write=False):
        project = get_project_for_user(pk, request.user, write=write)
        return get_object_or_404(ProjectFile, pk=file_id, project=project)

    def patch(self, request, pk, file_id):
        pf = self._get_file(request, pk, file_id, write=True)
        enabled = request.data.get('enabled')
        if enabled is not None:
            pf.enabled = bool(enabled)
            pf.save(update_fields=['enabled'])
        return Response(ProjectFileSerializer(pf, context={'request': request}).data)

    def delete(self, request, pk, file_id):
        pf = self._get_file(request, pk, file_id, write=True)
        filename = pf.filename
        project = pf.project
        try:
            pf.file.delete(save=False)
        except Exception:
            pass
        pf.delete()
        from aitext.tasks import _write_audit
        _write_audit(project, request.user, 'file_delete', target=filename)
        return Response(status=204)


class ProjectFileSearchView(APIView):
    """GET /api/v1/projects/<pk>/files/search/?q=<query>

    Sprint 5.3: гибридный FTS+вектор поиск по файлам базы знаний.
    Требует PROJECT_FILE_SEARCH=1 в .env (иначе 400).
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        from django.conf import settings
        if not getattr(settings, 'PROJECT_FILE_SEARCH', False):
            return Response({'error': em('file_search_disabled')}, status=400)

        project = get_project_for_user(pk, request.user, write=False)
        query = request.query_params.get('q', '').strip()

        if not query:
            files = project.knowledge_files.filter(status='ready', enabled=True).exclude(source='repo')
            return Response(ProjectFileSerializer(files, many=True, context={'request': request}).data)

        from aitext.search import search_knowledge
        results = search_knowledge(project, query, top_n=20)
        return Response(ProjectFileSerializer(results, many=True, context={'request': request}).data)


class FileVersionListView(APIView):
    """GET /api/v1/projects/<pk>/files/<file_id>/versions/

    Sprint 5.4: список снапшотов версий файла (последние 10).
    Требует PROJECT_FILE_VERSIONS=1.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, file_id):
        from django.conf import settings
        if not getattr(settings, 'PROJECT_FILE_VERSIONS', False):
            return Response({'error': em('file_versions_disabled')}, status=400)

        project = get_project_for_user(pk, request.user, write=False)
        pf = get_object_or_404(ProjectFile, pk=file_id, project=project)

        from aitext.models import ProjectFileVersion
        versions = ProjectFileVersion.objects.filter(file=pf).order_by('-created_at')[:10]
        data = [
            {
                'id': v.id,
                'repo_sha': v.repo_sha,
                'created_at': v.created_at.isoformat(),
                'content_preview': v.content_snapshot[:200],
                'size': len(v.content_snapshot),
            }
            for v in versions
        ]
        return Response(data)


class FileRestoreView(APIView):
    """POST /api/v1/projects/<pk>/files/<file_id>/versions/<version_id>/restore/

    Sprint 5.4: восстанавливает файл из снапшота версии.
    Перед восстановлением создаёт снапшот текущего содержимого.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, file_id, version_id):
        from django.conf import settings
        if not getattr(settings, 'PROJECT_FILE_VERSIONS', False):
            return Response({'error': em('file_versions_disabled')}, status=400)

        project = get_project_for_user(pk, request.user, write=True)
        pf = get_object_or_404(ProjectFile, pk=file_id, project=project)

        from aitext.models import ProjectFileVersion
        version = get_object_or_404(ProjectFileVersion, pk=version_id, file=pf)

        from aitext.sync import _create_version_snapshot
        _create_version_snapshot(pf, pf.extracted_text)

        pf.extracted_text = version.content_snapshot
        pf.embed_status = 'none'
        pf.save(update_fields=['extracted_text', 'embed_status'])

        if getattr(settings, 'PROJECT_VECTOR_RAG', False):
            from aitext.tasks import embed_project_file
            embed_project_file.delay(pf.id)

        return Response({'restored': True, 'version_id': version_id, 'file_id': file_id})
