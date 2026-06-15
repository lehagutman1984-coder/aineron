from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import StudioProject, StudioPipelineState
from ..serializers import StudioProjectSerializer, StudioProjectCreateSerializer


class StudioProjectListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return StudioProject.objects.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.request.method == 'POST':
            return StudioProjectCreateSerializer
        return StudioProjectSerializer

    def perform_create(self, serializer):
        project = serializer.save(user=self.request.user, status='draft')
        StudioPipelineState.objects.create(project=project)


class StudioProjectDetailView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StudioProjectSerializer
    lookup_field = 'id'

    def get_queryset(self):
        return StudioProject.objects.filter(user=self.request.user)


class InterviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        questions = project.interview_data.get('questions')
        if not questions:
            from ..tasks import agent_interview
            agent_interview.apply(args=[str(project.id)])
            project.refresh_from_db()
            questions = project.interview_data.get('questions', [])
        return Response({'questions': questions})

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        answers = request.data.get('answers', [])
        project.interview_data['answers'] = answers
        project.status = 'planning'
        project.save(update_fields=['interview_data', 'status'])
        from ..tasks import agent_analyze
        agent_analyze.delay(str(project.id))
        return Response({'status': 'planning'}, status=status.HTTP_202_ACCEPTED)


class CloneView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from ..security import is_safe_url
        url = request.data.get('url', '')
        if not is_safe_url(url):
            return Response({'error': 'Небезопасный URL'}, status=400)
        project = StudioProject.objects.create(
            user=request.user,
            name=request.data.get('name', 'Клон сайта'),
            entry_mode='clone_url',
            target_url=url,
            status='draft',
        )
        StudioPipelineState.objects.create(project=project)
        from ..tasks import crawl_and_analyze
        crawl_and_analyze.delay(str(project.id))
        return Response(StudioProjectSerializer(project).data, status=201)
