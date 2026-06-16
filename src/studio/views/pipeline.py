from django.http import StreamingHttpResponse
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from ..models import StudioProject
from ..serializers import PipelineStateSerializer
from ..events import get_pipeline_events


class PipelineStateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        return Response(PipelineStateSerializer(project.pipeline).data)


class PipelineRunView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        # Atomic guard: only dispatch if project is in a startable state
        triggered = StudioProject.objects.filter(
            id=id, user=request.user, status__in=['ready', 'paused']
        ).update(status='coding')
        if not triggered:
            project = StudioProject.objects.get(id=id, user=request.user)
            return Response({'status': project.status}, status=200)
        from ..tasks import run_pipeline
        run_pipeline.delay(str(id))
        return Response({'status': 'running'}, status=202)


class PipelineEventsView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        StudioProject.objects.get(id=id, user=request.user)

        def generator():
            yield 'data: {"type": "connected"}\n\n'
            for raw in get_pipeline_events(str(id)):
                yield f'data: {raw}\n\n'

        resp = StreamingHttpResponse(generator(), content_type='text/event-stream')
        resp['Cache-Control'] = 'no-cache'
        resp['X-Accel-Buffering'] = 'no'
        return resp


class PipelinePauseView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        from celery import current_app
        project = StudioProject.objects.get(id=id, user=request.user)
        state = project.pipeline
        state.status = 'paused_manual'
        state.pause_requested = True
        state.pause_reason = request.data.get('reason', 'Пауза пользователем')
        state.save(update_fields=['status', 'pause_requested', 'pause_reason'])
        if state.current_task_id:
            current_app.control.revoke(state.current_task_id, terminate=True, signal='SIGTERM')
        project.status = 'paused'
        project.save(update_fields=['status'])
        return Response({'status': 'paused_manual'})


class PipelineResumeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        from ..billing import estimate_stars, can_afford
        project = StudioProject.objects.get(id=id, user=request.user)
        state = project.pipeline
        action = request.data.get('action', 'continue')
        from ..tasks import coder_iteration, next_step
        state.pause_requested = False
        state.iteration_count = 0  # mandatory reset to avoid instant re-pause
        if action == 'with_hint':
            state.resume_hint = request.data.get('hint', '')
            state.fix_plan = {'instructions': state.resume_hint, 'target_files': []}
            state.status = 'running'
            state.save()
            coder_iteration.delay(str(project.id), state.step_index)
        elif action == 'skip_step':
            state.status = 'running'
            state.save()
            next_step.delay(str(project.id), state.step_index)
        else:
            state.status = 'running'
            state.save()
            coder_iteration.delay(str(project.id), state.step_index)
        remaining_steps = max(0, project.interview_data.get('planned_steps', 5) - state.step_index)
        low_balance = not can_afford(
            request.user,
            estimate_stars(project, planned_steps=remaining_steps),
        )
        return Response({'status': 'running', 'low_balance': low_balance})
