import requests as _rq
from django.http import StreamingHttpResponse, HttpResponse
from rest_framework import permissions
from rest_framework.views import APIView
from rest_framework.response import Response
from ..models import StudioProject
from ..serializers import PipelineStateSerializer
from ..events import get_pipeline_events
from ..billing import estimate_stars


class EstimateView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        planned = project.interview_data.get('planned_steps')
        if not planned:
            from ..tasks import _split_steps
            planned = len(_split_steps(project.commits_md_content)) or 5
        est = estimate_stars(project, planned_steps=planned)
        return Response({
            'estimated_stars': est,
            'planned_steps': planned,
            'balance': request.user.pages_count,
            'affordable': request.user.pages_count >= est,
        })


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


class ApproveStepView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        state = project.pipeline
        state.status = 'running'
        state.pause_requested = False
        state.save(update_fields=['status', 'pause_requested'])
        project.status = 'coding'
        project.save(update_fields=['status'])
        from ..tasks import next_step
        next_step.delay(str(project.id), state.step_index)
        return Response({'status': 'running'})


class ContextChatView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..agents.assistant import AssistantAgent
        from ..billing import can_afford, charge
        cost = 1
        if not can_afford(request.user, cost):
            return Response({'error': 'Недостаточно звёзд'}, status=402)
        msg = request.data.get('message', '')
        history = project.interview_data.get('assistant_history', [])
        answer = AssistantAgent(project).answer(msg, history)
        charge(request.user, cost, project)
        history += [{'role': 'user', 'text': msg}, {'role': 'assistant', 'text': answer}]
        project.interview_data['assistant_history'] = history[-20:]
        project.save(update_fields=['interview_data'])
        return Response({'answer': answer})


class DeployView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import deploy_to_vercel
        deploy_to_vercel.delay(str(project.id))
        return Response({'status': 'deploying'}, status=202)


class PreviewRestartView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..tasks import restart_preview
        restart_preview.delay(str(project.id))
        return Response({'status': 'restarting'}, status=202)


class SandboxStatusView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        cid = project.sandbox_container_id
        if not cid:
            return Response({'alive': False, 'port': project.preview_port, 'uptime_s': 0})
        alive = False
        uptime_s = 0
        try:
            from .. import sandbox as _sb
            client = _sb.get_docker()
            container = client.containers.get(cid)
            alive = container.status == 'running'
            started = container.attrs.get('State', {}).get('StartedAt', '')
            if alive and started:
                import datetime
                start = datetime.datetime.fromisoformat(started[:19])
                uptime_s = int((datetime.datetime.utcnow() - start).total_seconds())
        except Exception:
            alive = False
        return Response({'alive': alive, 'port': project.preview_port, 'uptime_s': uptime_s})


class ExplainView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..billing import can_afford, charge
        cost = 1
        if not can_afford(request.user, cost):
            return Response({'error': 'Недостаточно звёзд'}, status=402)
        code = request.data.get('code', '')
        path = request.data.get('path', '')
        if not code.strip():
            return Response({'error': 'Пустой фрагмент'}, status=400)
        from ..agents.explainer import ExplainerAgent
        answer = ExplainerAgent(project).explain(code, path)
        charge(request.user, cost, project)
        return Response({'explanation': answer})


class PreviewProxyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id, path=''):
        project = StudioProject.objects.get(id=id, user=request.user)
        if not project.sandbox_container_id:
            return HttpResponse('Sandbox не запущен', status=503)
        host = project.sandbox_container_id
        try:
            upstream = _rq.get(
                f'http://{host}:3000/{path}',
                timeout=10,
                headers={'Accept': request.headers.get('Accept', '*/*')},
            )
        except Exception:
            return HttpResponse('Preview недоступен', status=502)
        resp = HttpResponse(upstream.content, status=upstream.status_code)
        ct = upstream.headers.get('Content-Type')
        if ct:
            resp['Content-Type'] = ct
        return resp
