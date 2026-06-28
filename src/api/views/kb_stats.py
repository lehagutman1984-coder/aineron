"""Sprint 5 — KB Health Dashboard: file status, chunk counts, re-index."""
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from aitext.models import Project, ProjectFile


class ProjectKBStatsView(APIView):
    """GET /v1/projects/<pk>/kb/stats/ — статистика базы знаний проекта."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        project = get_object_or_404(Project, id=pk, user=request.user)
        files = list(project.knowledge_files.prefetch_related('chunks').order_by('created_at'))

        files_data = []
        total_chunks = 0
        indexed_count = 0
        pending_count = 0
        error_count = 0
        disabled_count = 0

        for f in files:
            chunk_count = len(f.chunks.all())
            total_chunks += chunk_count

            if not f.enabled:
                disabled_count += 1
            elif f.embed_status == 'done':
                indexed_count += 1
            elif f.embed_status == 'error':
                error_count += 1
            else:
                pending_count += 1

            files_data.append({
                'id': f.id,
                'filename': f.filename,
                'file_type': f.file_type,
                'status': f.status,
                'embed_status': f.embed_status,
                'enabled': f.enabled,
                'chunk_count': chunk_count,
                'file_size': f.file_size,
                'source': f.source,
                'created_at': f.created_at,
            })

        return Response({
            'file_count': len(files),
            'indexed_count': indexed_count,
            'pending_count': pending_count,
            'error_count': error_count,
            'disabled_count': disabled_count,
            'total_chunks': total_chunks,
            'files': files_data,
        })


class ProjectFileChunksView(APIView):
    """GET /v1/projects/<pk>/files/<file_id>/chunks/ — список чанков файла."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, file_id):
        project = get_object_or_404(Project, id=pk, user=request.user)
        f = get_object_or_404(ProjectFile, id=file_id, project=project)
        chunks = f.chunks.order_by('chunk_index').values('id', 'chunk_index', 'content', 'token_count')
        return Response(list(chunks))


class ProjectFileReindexView(APIView):
    """POST /v1/projects/<pk>/files/<file_id>/reindex/ — запускает переиндексацию файла."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk, file_id):
        project = get_object_or_404(Project, id=pk, user=request.user)
        f = get_object_or_404(ProjectFile, id=file_id, project=project)

        f.embed_status = 'pending'
        f.save(update_fields=['embed_status'])

        try:
            from aitext.tasks import embed_project_file
            embed_project_file.delay(file_id)
        except Exception:
            pass

        return Response({'ok': True, 'embed_status': 'pending'})
