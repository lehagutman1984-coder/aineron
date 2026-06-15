from rest_framework import generics, permissions
from ..models import StudioProject, StudioFile
from ..serializers import StudioFileSerializer, StudioFileDetailSerializer


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
