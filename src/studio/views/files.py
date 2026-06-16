import io
import zipfile
from django.http import HttpResponse
from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import StudioProject, StudioFile
from ..serializers import StudioFileSerializer, StudioFileDetailSerializer, StudioVersionSerializer


class FileTreeView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        return StudioFileDetailSerializer if self.request.method == 'POST' else StudioFileSerializer

    def get_queryset(self):
        return StudioFile.objects.filter(
            project_id=self.kwargs['id'],
            project__user=self.request.user,
        )

    def perform_create(self, serializer):
        project = StudioProject.objects.get(id=self.kwargs['id'], user=self.request.user)
        instance = serializer.save(project=project, last_modified_by='user')
        from ..tasks import sync_manual_edit
        sync_manual_edit.delay(str(project.id), instance.pk)


class FileDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StudioFileDetailSerializer
    lookup_field = 'pk'
    lookup_url_kwarg = 'file_id'

    def get_queryset(self):
        return StudioFile.objects.filter(
            project_id=self.kwargs['id'],
            project__user=self.request.user,
        )

    def perform_update(self, serializer):
        instance = serializer.save(last_modified_by='user')
        from ..tasks import sync_manual_edit
        sync_manual_edit.delay(str(self.kwargs['id']), instance.pk)

    def perform_destroy(self, instance):
        project_id = str(self.kwargs['id'])
        path = instance.path
        cid = instance.project.sandbox_container_id
        instance.delete()
        if cid:
            from ..tasks import delete_sandbox_file
            delete_sandbox_file.delay(project_id, path)


class FileDiffView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id, file_id):
        from .. import gitea_client
        f = StudioFile.objects.get(pk=file_id, project_id=id, project__user=request.user)
        project = f.project
        ref = request.query_params.get('ref')
        old = ''
        if ref and project.repo_url and project.user.gitea_username:
            owner = project.user.gitea_username
            repo = project.repo_url.rstrip('/').split('/')[-1]
            old = gitea_client.get_file_content(owner, repo, f.path, ref=ref) or ''
        return Response({'path': f.path, 'old': old, 'new': f.content})


class CommitHistoryView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        return Response(StudioVersionSerializer(project.versions.all(), many=True).data)


class RollbackView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id, version_id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import rollback_to_version
        rollback_to_version.delay(str(project.id), version_id)
        return Response({'status': 'rolling_back'})


class ExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
            for f in project.files.all():
                zf.writestr(f.path.lstrip('/'), f.content)
        buf.seek(0)
        resp = HttpResponse(buf.read(), content_type='application/zip')
        safe_name = project.name.replace(' ', '_')[:50]
        resp['Content-Disposition'] = f'attachment; filename="{safe_name}.zip"'
        return resp


class SearchFilesView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        q = (request.query_params.get('q') or '').strip()
        if not q:
            return Response([])
        files = StudioFile.objects.filter(
            project_id=id, project__user=request.user, content__icontains=q,
        )
        results = []
        for f in files[:50]:
            file_hits = 0
            for i, line in enumerate(f.content.splitlines(), start=1):
                if q.lower() in line.lower():
                    results.append({
                        'file_id': f.id, 'path': f.path,
                        'line': i, 'snippet': line.strip()[:200],
                    })
                    file_hits += 1
                    if file_hits >= 5:
                        break
        return Response(results[:100])
