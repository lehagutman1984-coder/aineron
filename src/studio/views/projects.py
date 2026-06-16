from django.db.models import Q
from rest_framework import generics, permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView
from ..models import StudioProject, StudioPipelineState, StudioTemplate, StudioCollaborator
from ..serializers import (
    StudioProjectSerializer, StudioProjectCreateSerializer,
    StudioTemplateSerializer,
)


def accessible_projects(user):
    """Projects owned by user or where user is a collaborator."""
    return StudioProject.objects.filter(
        Q(user=user) | Q(collaborators__user=user)
    ).distinct()


class StudioProjectListCreateView(generics.ListCreateAPIView):
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return accessible_projects(self.request.user)

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
        return accessible_projects(self.request.user)

    def perform_destroy(self, instance):
        if instance.sandbox_container_id:
            from .. import sandbox
            sandbox.kill_sandbox(instance.sandbox_container_id)
        instance.delete()


class InterviewView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        # Atomic check-and-set: only the first request with status='draft' triggers the task
        triggered = StudioProject.objects.filter(
            id=id, user=request.user, status='draft'
        ).update(status='interview')

        project = StudioProject.objects.get(id=id, user=request.user)

        if triggered:
            project.interview_data.pop('interview_error', None)
            project.save(update_fields=['interview_data'])
            from ..tasks import agent_interview
            agent_interview.delay(str(project.id))

        questions = project.interview_data.get('questions') or []
        interview_error = project.interview_data.get('interview_error')
        resp = {'questions': questions, 'status': project.status}
        if interview_error:
            resp['interview_error'] = interview_error
        return Response(resp)

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        answers = request.data.get('answers', [])
        project.interview_data['answers'] = answers
        project.status = 'planning'
        project.save(update_fields=['interview_data', 'status'])
        from ..tasks import agent_analyze
        agent_analyze.delay(str(project.id))
        return Response({'status': 'planning'}, status=status.HTTP_202_ACCEPTED)


class TemplateListView(generics.ListAPIView):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = StudioTemplateSerializer

    def get_queryset(self):
        return StudioTemplate.objects.filter(is_public=True)


class PublishTemplateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        import re
        project = StudioProject.objects.get(id=id, user=request.user)
        slug_base = re.sub(r'[^a-z0-9]+', '-', project.name.lower()).strip('-') or 'template'
        slug = slug_base
        counter = 1
        while StudioTemplate.objects.filter(slug=slug).exists():
            slug = f'{slug_base}-{counter}'
            counter += 1
        template = StudioTemplate.objects.create(
            slug=slug,
            name=project.name,
            description=project.description or project.name,
            stack=project.target_stack,
            seed_prompt=(project.description + '\n\n' + project.project_md_content)[:2000],
            author=request.user,
            is_public=True,
        )
        return Response({'id': template.id, 'slug': template.slug}, status=201)


class CollaboratorView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        action = request.data.get('action', 'add')
        email = request.data.get('email', '').strip()
        if not email:
            return Response({'error': 'Email обязателен'}, status=400)
        from django.contrib.auth import get_user_model
        User = get_user_model()
        try:
            target = User.objects.get(email=email)
        except User.DoesNotExist:
            return Response({'error': 'Пользователь не найден'}, status=404)
        if action == 'remove':
            StudioCollaborator.objects.filter(project=project, user=target).delete()
            return Response({'status': 'removed'})
        role = request.data.get('role', 'viewer')
        collab, _ = StudioCollaborator.objects.get_or_create(project=project, user=target)
        collab.role = role
        collab.save(update_fields=['role'])
        return Response({'status': 'added', 'role': role}, status=201)


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
