from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import StudioProject, StudioFile
from ..serializers import StudioFileSerializer, StudioFileDetailSerializer, StudioVersionSerializer


class FileTreeView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StudioFileSerializer

    def get_queryset(self):
        return StudioFile.objects.filter(
            project_id=self.kwargs['id'],
            project__user=self.request.user,
        )


class FileDetailView(generics.RetrieveUpdateAPIView):
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
        serializer.save(last_modified_by='user')


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
