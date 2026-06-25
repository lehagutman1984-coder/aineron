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
            try:
                from .. import sandbox
                sandbox.kill_sandbox(instance.sandbox_container_id)
            except Exception:
                pass
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
            # Interview disabled: skip straight to planning with empty answers
            project.interview_data.pop('interview_error', None)
            project.interview_data['answers'] = []
            project.status = 'planning'
            project.save(update_fields=['interview_data', 'status'])
            from ..tasks import agent_analyze
            agent_analyze.delay(str(project.id))

        return Response({'questions': [], 'status': project.status})

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


class ScreenshotView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        import base64
        project = StudioProject.objects.get(id=id, user=request.user)
        img = request.FILES.get('image')
        if not img:
            return Response({'error': 'Нет файла'}, status=400)
        project.screenshot = img
        project.save(update_fields=['screenshot'])
        img.seek(0)
        b64 = base64.b64encode(img.read()).decode()
        from ..agents.screenshot import ScreenshotAgent
        desc = ScreenshotAgent(project).describe(b64)
        project.interview_data['screenshot_description'] = desc
        project.save(update_fields=['interview_data'])
        return Response({'description': desc})


class TimelineView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import _split_steps
        steps = _split_steps(project.commits_md_content)
        changed = project.interview_data.get('last_changed', {})
        versions = {v.step_index: v for v in project.versions.all()}
        out = []
        for i, text in enumerate(steps):
            v = versions.get(i)
            out.append({
                'step_index': i,
                'name': text.strip().splitlines()[0][:120] if text.strip() else f'Шаг {i}',
                'planned': text[:2000],
                'changed_files': changed.get(str(i), []),
                'version_id': v.id if v else None,
                'git_sha': v.git_sha if v else '',
            })
        return Response(out)


class BranchFromVersionView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id, version_id):
        from ..models import StudioVersion, StudioFile
        project = StudioProject.objects.get(id=id, user=request.user)
        version = StudioVersion.objects.get(id=version_id, project=project)
        fork = StudioProject.objects.create(
            user=request.user,
            name=f'{project.name} (ветка от шага {version.step_index})',
            description=project.description,
            mode=project.mode, entry_mode=project.entry_mode,
            target_url=project.target_url, target_stack=project.target_stack,
            project_md_content=project.project_md_content,
            commits_md_content=project.commits_md_content,
            interview_data=project.interview_data,
            forked_from=project, status='ready',
        )
        StudioPipelineState.objects.create(project=fork)
        for f in project.files.all():
            StudioFile.objects.create(project=fork, path=f.path, content=f.content, language=f.language)
        return Response({'id': str(fork.id)}, status=201)


class GithubExportView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import export_to_github
        repo_name = request.data.get('repo_name', f'aineron-{str(project.id)[:8]}')
        private = bool(request.data.get('private', True))
        export_to_github.delay(str(project.id), repo_name, private)
        return Response({'status': 'exporting'}, status=202)


class NotificationPrefsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def put(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        project.interview_data['notify'] = {
            'email': bool(request.data.get('email', True)),
            'telegram': bool(request.data.get('telegram', False)),
            'push': bool(request.data.get('push', False)),
        }
        project.save(update_fields=['interview_data'])
        return Response(project.interview_data['notify'])


class DeviationView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id, n):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import _split_steps
        steps = _split_steps(project.commits_md_content)
        planned = steps[n] if n < len(steps) else ''
        changed_paths = (project.interview_data.get('last_changed', {})).get(str(n), [])
        files = {f.path: f.content for f in project.files.filter(path__in=changed_paths)}
        from ..agents.deviation import DeviationReviewerAgent
        report = DeviationReviewerAgent(project).review(planned, files)
        return Response(report)


class ProjectSettingsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    ALLOWED = {'ai_model', 'agent_models', 'max_iterations', 'max_stars_budget', 'auto_deploy', 'mode'}

    def patch(self, request, id):
        from ..models_catalog import MODEL_TIER
        project = StudioProject.objects.get(id=id, user=request.user)

        # Validate before applying
        if 'ai_model' in request.data:
            if request.data['ai_model'] not in MODEL_TIER:
                return Response({'error': f"Неизвестная модель: {request.data['ai_model']}"}, status=400)
        if 'agent_models' in request.data:
            am = request.data['agent_models']
            if not isinstance(am, dict):
                return Response({'error': 'agent_models должен быть объектом'}, status=400)
            invalid = [v for v in am.values() if v not in MODEL_TIER]
            if invalid:
                return Response({'error': f'Неизвестные модели: {", ".join(invalid)}'}, status=400)
        for k in ('max_iterations', 'max_stars_budget'):
            if k in request.data:
                val = request.data[k]
                if not isinstance(val, int) or val < 0:
                    return Response({'error': f'{k} должен быть неотрицательным числом'}, status=400)

        updated = []
        for key in self.ALLOWED:
            if key in request.data:
                setattr(project, key, request.data[key])
                updated.append(key)
        if updated:
            project.save(update_fields=updated)
        return Response({
            'ai_model': project.ai_model,
            'agent_models': project.agent_models or {},
            'max_iterations': project.max_iterations,
            'max_stars_budget': project.max_stars_budget,
            'auto_deploy': project.auto_deploy,
            'mode': project.mode,
        })


class ModelsCatalogView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from ..models_catalog import STUDIO_MODELS
        return Response(STUDIO_MODELS)
