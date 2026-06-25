import os as _os

import requests as _rq
from django.http import StreamingHttpResponse, HttpResponse
from django.utils.decorators import method_decorator
from django.views.decorators.clickjacking import xframe_options_exempt
from rest_framework import permissions
from rest_framework.renderers import BaseRenderer
from rest_framework.views import APIView
from rest_framework.response import Response
from ..models import StudioProject, ProjectDatabase
from ..serializers import PipelineStateSerializer
from ..events import get_pipeline_events
from ..billing import estimate_stars

_PREVIEW_SVC = _os.environ.get('PREVIEW_SERVICE_URL', 'http://localhost:8001')
_PREVIEW_TOKEN = _os.environ.get('PREVIEW_INTERNAL_TOKEN', '')


def _preview_headers():
    return {'X-Internal-Token': _PREVIEW_TOKEN, 'Content-Type': 'application/json'}


class EventStreamRenderer(BaseRenderer):
    """Allow DRF to accept Accept: text/event-stream without returning 406."""
    media_type = 'text/event-stream'
    format = 'event-stream'

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


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
    renderer_classes = [EventStreamRenderer]

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


class PipelineResetView(APIView):
    """Kill a stuck pipeline. Pass restart=true to reset to 'ready' for re-run."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        from celery import current_app
        from ..tasks import _timeout_pipeline, release_reserve
        from .. import sandbox as _sandbox
        project = StudioProject.objects.get(id=id, user=request.user)
        state = project.pipeline
        if state.current_task_id:
            try:
                current_app.control.revoke(state.current_task_id, terminate=True, signal='SIGTERM')
            except Exception:
                pass
        restart = bool(request.data.get('restart', False))
        if restart:
            # Reset to 'ready' so user can re-run without deleting
            state.status = 'idle'
            state.pause_requested = False
            state.current_task_id = ''
            state.save(update_fields=['status', 'pause_requested', 'current_task_id'])
            project.status = 'ready'
            project.save(update_fields=['status'])
            try:
                release_reserve(project)
            except Exception:
                pass
            return Response({'status': 'ready'})
        _timeout_pipeline(state, 'Отменено пользователем')
        return Response({'status': 'failed'})


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
        state.autofix_count = 0
        state.seen_error_hashes = []
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
        from ..tasks import deploy_to_vercel, deploy_to_timeweb, deploy_to_selectel
        target = request.data.get('target', getattr(project, 'deploy_target', 'vercel') or 'vercel')
        task = {
            'vercel': deploy_to_vercel,
            'timeweb': deploy_to_timeweb,
            'selectel': deploy_to_selectel,
        }.get(target, deploy_to_vercel)
        task.delay(str(project.id))
        return Response({'status': 'deploying', 'target': target}, status=202)


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
        from django.conf import settings as djsettings
        project = StudioProject.objects.get(id=id, user=request.user)

        # Sprint 6: frontend stacks handled by Sandpack — no Docker sandbox needed
        _FRONTEND_STACKS = ('react', 'vue', 'html', 'tma')
        if getattr(djsettings, 'STUDIO_DEPRECATE_DOCKER_FRONTEND', True) and project.target_stack in _FRONTEND_STACKS:
            return Response({'alive': False, 'port': None, 'uptime_s': 0, 'sandpack': True})

        cid = project.sandbox_container_id

        # Static mode: no sandbox needed — files served directly from DB
        if not cid:
            has_files = project.files.exists()
            return Response({'alive': has_files, 'port': 3000, 'uptime_s': 0, 'static': True})

        container_running = False
        uptime_s = 0
        try:
            from .. import sandbox as _sb
            client = _sb.get_docker()
            container = client.containers.get(cid)
            container_running = container.status == 'running'
            started = container.attrs.get('State', {}).get('StartedAt', '')
            if container_running and started:
                import datetime
                start = datetime.datetime.fromisoformat(started[:19])
                uptime_s = int((datetime.datetime.utcnow() - start).total_seconds())
        except Exception:
            container_running = False
        alive = False
        if container_running:
            try:
                from .. import sandbox as _sb
                alive = _sb.is_http_alive(cid)
            except Exception:
                alive = False
        # If sandbox check fails, fall back to static serving
        if not alive:
            has_files = project.files.exists()
            return Response({'alive': has_files, 'port': 3000, 'uptime_s': uptime_s, 'static': True})
        return Response({'alive': alive, 'port': project.preview_port, 'uptime_s': uptime_s, 'static': False})


class PipelineSkipView(APIView):
    """Skip the current stuck step (resets anti-loop counters) and move to the next."""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        from ..events import publish_event
        project = StudioProject.objects.get(id=id, user=request.user)
        state = project.pipeline
        state.status = 'running'
        state.pause_requested = False
        state.same_diff_count = 0
        state.last_files_hash = ''
        state.last_error_signature = ''
        state.error_repeat_count = 0
        state.autofix_count = 0
        state.seen_error_hashes = []
        state.save(update_fields=[
            'status', 'pause_requested', 'same_diff_count',
            'last_files_hash', 'last_error_signature', 'error_repeat_count',
            'autofix_count', 'seen_error_hashes',
        ])
        project.status = 'coding'
        project.save(update_fields=['status'])
        from ..tasks import next_step
        next_step.delay(str(project.id), state.step_index)
        publish_event(str(project.id), {'agent': 'system', 'level': 'info', 'type': 'resumed', 'action': 'skip_step'})
        return Response({'status': 'running', 'skipped_step': state.step_index})


class ConsoleErrorView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        err = {
            'message': request.data.get('message', '')[:1000],
            'stack': request.data.get('stack', '')[:2000],
            'file': request.data.get('file', ''),
            'line': request.data.get('line'),
        }
        errors = project.interview_data.setdefault('console_errors', [])
        errors.append(err)
        project.interview_data['console_errors'] = errors[-20:]
        project.save(update_fields=['interview_data'])
        if request.data.get('autofix'):
            import hashlib
            from django.conf import settings as _s
            from ..events import publish_event as _pub
            state = project.pipeline
            if _s.STUDIO_V4_AUTOFIX:
                sig = hashlib.sha256(
                    f"{err['message']}|{err['file']}".encode()
                ).hexdigest()[:16]
                seen = state.seen_error_hashes or []
                if sig in seen:
                    return Response({'error': 'duplicate_error', 'stored': True}, status=409)
                if (state.autofix_count or 0) >= _s.STUDIO_MAX_AUTOFIX:
                    state.status = 'paused_on_loop'
                    state.pause_reason = (
                        f'Достигнут лимит автоисправлений ({_s.STUDIO_MAX_AUTOFIX}). '
                        'Опишите проблему вручную.'
                    )
                    project.status = 'paused'
                    project.save(update_fields=['status'])
                    state.save(update_fields=['status', 'pause_reason'])
                    _pub(str(project.id), {
                        'agent': 'system', 'level': 'warning', 'type': 'paused',
                        'reason': state.pause_reason,
                    })
                    return Response({'paused': True, 'reason': 'autofix_limit'}, status=409)
                seen.append(sig)
                state.seen_error_hashes = seen[-50:]
                state.autofix_count = (state.autofix_count or 0) + 1

            hint = f"Ошибка в превью: {err['message']} ({err['file']}:{err['line']})\n{err['stack']}"
            state.fix_plan = {
                'instructions': hint,
                'target_files': [err['file']] if err['file'] else [],
            }
            state.status = 'running'
            state.pause_requested = False
            save_fields = ['fix_plan', 'status', 'pause_requested']
            if _s.STUDIO_V4_AUTOFIX:
                save_fields += ['seen_error_hashes', 'autofix_count']
            state.save(update_fields=save_fields)
            from ..tasks import coder_iteration
            coder_iteration.delay(str(project.id), state.step_index)
        return Response({'stored': True, 'count': len(project.interview_data['console_errors'])})


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


class ProjectDatabaseView(APIView):
    """
    Sprint 3 — code-complete, not integration-tested.

    Manage a Studio project's preview database binding. Secrets (Neon API key,
    external DSN) are Fernet-encrypted before persistence and never returned in
    clear. Provisioning itself is deferred: we save the binding and set
    provisioned=False; the preview-service E2BRuntime provisions lazily on start.
    """
    permission_classes = [permissions.IsAuthenticated]

    _VALID_MODES = {'aineron', 'neon', 'external'}

    def get(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        db = ProjectDatabase.objects.filter(project=project).first()
        if not db:
            return Response({
                'mode': 'none',
                'provisioned': False,
                'aineron_schema': '',
                'neon_project_id': '',
                'has_neon_key': False,
                'has_external_conn': False,
            })
        return Response({
            'mode': db.mode,
            'provisioned': db.provisioned,
            'aineron_schema': db.aineron_schema,
            'neon_project_id': db.neon_project_id,
            'has_neon_key': bool(db.neon_api_key_enc),
            'has_external_conn': bool(db.external_conn_enc),
        })

    def post(self, request, id):
        from aitext.crypto import encrypt_token
        project = StudioProject.objects.get(id=id, user=request.user)
        mode = request.data.get('mode', '')
        if mode not in self._VALID_MODES:
            return Response({'error': 'Недопустимый режим базы данных'}, status=400)

        db, _ = ProjectDatabase.objects.get_or_create(project=project)
        db.mode = mode
        # New mode invalidates any prior provisioned credentials.
        db.provisioned = False
        db.credentials_enc = ''
        db.aineron_schema = ''
        db.neon_project_id = ''

        if mode == 'neon':
            neon_api_key = (request.data.get('neon_api_key') or '').strip()
            if not neon_api_key and not db.neon_api_key_enc:
                return Response({'error': 'Требуется Neon API-ключ'}, status=400)
            if neon_api_key:
                db.neon_api_key_enc = encrypt_token(neon_api_key)
            db.external_conn_enc = ''
        elif mode == 'external':
            external_conn = (request.data.get('external_conn') or '').strip()
            if not external_conn and not db.external_conn_enc:
                return Response({'error': 'Требуется строка подключения'}, status=400)
            if external_conn:
                if not external_conn.startswith(('postgresql://', 'postgres://')):
                    return Response({'error': 'DSN должен начинаться с postgresql://'}, status=400)
                db.external_conn_enc = encrypt_token(external_conn)
            db.neon_api_key_enc = ''
        else:  # aineron — no user secrets
            db.neon_api_key_enc = ''
            db.external_conn_enc = ''

        db.save()
        return Response({'ok': True, 'mode': mode})

    def delete(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        db = ProjectDatabase.objects.filter(project=project).first()
        if db:
            db.mode = 'none'
            db.provisioned = False
            db.credentials_enc = ''
            db.neon_api_key_enc = ''
            db.external_conn_enc = ''
            db.aineron_schema = ''
            db.neon_project_id = ''
            db.save()
        return Response({'ok': True, 'mode': 'none'})


class DbExportView(APIView):
    """
    Sprint 6: Export project database as SQL dump (Aineron schema only).
    GET /studio/projects/{id}/db/export/ → streaming SQL file download.
    Only supports mode='aineron'. For Neon/External the user manages their own DB.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id):
        import subprocess
        import tempfile
        from django.http import FileResponse
        from django.conf import settings as djsettings

        project = StudioProject.objects.get(id=id, user=request.user)
        db = ProjectDatabase.objects.filter(project=project).first()
        if not db or db.mode != 'aineron' or not db.aineron_schema:
            return Response(
                {'error': 'Экспорт доступен только для режима Aineron. Для Neon/External используйте собственный инструмент БД.'},
                status=400,
            )

        schema = db.aineron_schema
        host = _os.getenv('AINERON_DB_HOST', 'localhost')
        port = _os.getenv('AINERON_DB_PORT', '5432')
        db_name = _os.getenv('AINERON_DB_NAME', 'aineron')
        db_user = _os.getenv('AINERON_DB_USER', 'aineron')
        db_pass = _os.getenv('AINERON_DB_PASSWORD', '')

        env = dict(_os.environ)
        env['PGPASSWORD'] = db_pass

        try:
            tmp = tempfile.NamedTemporaryFile(suffix='.sql', delete=False, prefix=f'export_{schema}_')
            tmp.close()
            result = subprocess.run(
                [
                    'pg_dump',
                    '-h', host,
                    '-p', port,
                    '-U', db_user,
                    '-d', db_name,
                    '-n', schema,
                    '--no-owner',
                    '--no-acl',
                    '-f', tmp.name,
                ],
                env=env,
                capture_output=True,
                timeout=30,
            )
            if result.returncode != 0:
                return Response({'error': f'pg_dump error: {result.stderr.decode()[:300]}'}, status=502)

            response = FileResponse(
                open(tmp.name, 'rb'),
                content_type='application/sql',
                as_attachment=True,
                filename=f'{schema}_export.sql',
            )
            return response
        except FileNotFoundError:
            return Response({'error': 'pg_dump не найден на сервере'}, status=501)
        except subprocess.TimeoutExpired:
            return Response({'error': 'pg_dump timeout (>30 s)'}, status=504)


class E2BPreviewView(APIView):
    """
    POST → start E2B preview session (collects project files, delegates to preview-service).
    DELETE /{session_id}/ → stop session.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        stack = project.target_stack
        if stack not in ('nextjs', 'python', 'django'):
            return Response({'error': f'E2B не поддерживает стек {stack} в Sprint 2'}, status=400)

        files = project.files.all().values('path', 'content')
        code_files = {f['path']: f['content'] for f in files}

        try:
            resp = _rq.post(
                f'{_PREVIEW_SVC}/preview/start',
                json={
                    'project_id': str(project.id),
                    'stack': stack,
                    'code_files': code_files,
                    'ttl': 900,
                    'env': {},
                    'user_id': str(request.user.id),  # Sprint 6: per-user rate limiting
                },
                headers=_preview_headers(),
                timeout=30,
            )
        except _rq.exceptions.ConnectionError:
            return Response(
                {'error': 'preview-service недоступен. Запустите: cd preview-service && uvicorn main:app --port 8001'},
                status=503,
            )

        if resp.status_code == 429:
            return Response({'error': resp.json().get('detail', 'Слишком много превью')}, status=429)
        if not resp.ok:
            return Response({'error': resp.text[:500]}, status=502)

        return Response(resp.json())

    def delete(self, request, id, session_id):
        StudioProject.objects.get(id=id, user=request.user)  # auth check
        try:
            _rq.delete(
                f'{_PREVIEW_SVC}/preview/{session_id}',
                headers=_preview_headers(),
                timeout=10,
            )
        except Exception:
            pass
        return Response({'ok': True})


class E2BPreviewStatusView(APIView):
    """GET → status, DELETE → stop session."""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id, session_id):
        StudioProject.objects.get(id=id, user=request.user)  # auth check
        try:
            resp = _rq.get(
                f'{_PREVIEW_SVC}/preview/{session_id}/status',
                headers=_preview_headers(),
                timeout=5,
            )
        except _rq.exceptions.ConnectionError:
            return Response({'state': 'stopped', 'public_url': None, 'logs_tail': []})
        if not resp.ok:
            return Response({'state': 'stopped', 'public_url': None, 'logs_tail': []})
        return Response(resp.json())

    def delete(self, request, id, session_id):
        StudioProject.objects.get(id=id, user=request.user)  # auth check
        try:
            _rq.delete(
                f'{_PREVIEW_SVC}/preview/{session_id}',
                headers=_preview_headers(),
                timeout=10,
            )
        except Exception:
            pass
        return Response({'ok': True})


class BotEmulateView(APIView):
    """
    Tier 1 Telegram Bot emulator: uses AI to simulate bot responses
    given the project's source files as context.
    No Telegram, no execution — pure LLM simulation.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        from ..billing import can_afford, charge
        cost = 1
        if not can_afford(request.user, cost):
            return Response({'error': 'Недостаточно звёзд'}, status=402)

        message = str(request.data.get('message', ''))[:500]
        if not message.strip():
            return Response({'error': 'Пустое сообщение'}, status=400)

        # Build context from project's Python files (first 10, max 1500 chars each)
        files_ctx = ''
        for f in project.files.filter(path__endswith='.py').order_by('path')[:10]:
            files_ctx += f'\n--- {f.path} ---\n{f.content[:1500]}'
        if not files_ctx:
            files_ctx = '(файлы бота ещё не созданы)'

        system = (
            'Ты симулируешь Telegram-бота. Исходный код бота:\n'
            f'{files_ctx}\n\n'
            'Отвечай строго как этот бот, используя его логику, команды и текст ответов. '
            'Ответ должен быть кратким (до 200 символов) и соответствовать поведению бота.'
        )

        try:
            from ..agents.base import get_client
            client = get_client()
            completion = client.chat.completions.create(
                model='deepseek-v3.2',
                messages=[
                    {'role': 'system', 'content': system},
                    {'role': 'user', 'content': message},
                ],
                max_tokens=300,
                temperature=0.3,
            )
            reply = completion.choices[0].message.content or '(нет ответа)'
        except Exception as exc:
            return Response({'error': f'Ошибка LLM: {exc}'}, status=502)

        charge(request.user, cost, project)
        return Response({'reply': reply})


class E2BBotPreviewView(APIView):
    """
    Sprint 5 Tier 2: run real Telegram bot in E2B sandbox.
    Bot token is passed only in-memory (request → preview-service env), never stored.
    """
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, id):
        project = StudioProject.objects.get(id=id, user=request.user)
        if project.target_stack != 'telegram_bot':
            return Response({'error': 'Проект не является Telegram Bot'}, status=400)

        bot_token = str(request.data.get('bot_token', '')).strip()
        if not bot_token or ':' not in bot_token:
            return Response(
                {'error': 'Неверный формат токена. Получите тестовый токен у @BotFather.'},
                status=400,
            )

        # SECURITY: Never log the token. Log only a safe prefix marker.
        files = project.files.all().values('path', 'content')
        code_files = {f['path']: f['content'] for f in files}

        try:
            resp = _rq.post(
                f'{_PREVIEW_SVC}/preview/start',
                json={
                    'project_id': str(project.id),
                    'stack': 'telegram_bot',
                    'code_files': code_files,
                    'ttl': 900,
                    'env': {'TELEGRAM_BOT_TOKEN': bot_token},  # token in-transit only
                },
                headers=_preview_headers(),
                timeout=30,
            )
        except _rq.exceptions.ConnectionError:
            return Response({'error': 'preview-service недоступен'}, status=503)
        finally:
            del bot_token  # discard from local scope immediately

        if resp.status_code == 409:
            return Response(
                {'error': 'Этот бот уже запущен в другой сессии. Остановите её перед новым запуском.'},
                status=409,
            )
        if not resp.ok:
            return Response({'error': resp.text[:300]}, status=502)

        data = resp.json()
        return Response({
            'session_id': data['session_id'],
            'state': data.get('state', 'starting'),
            'warning': (
                'Токен передан в изолированную E2B среду и хранится только в памяти sandbox. '
                'Сессия автоматически завершится через 15 мин.'
            ),
        })


_MIME = {
    '.html': 'text/html; charset=utf-8',
    '.htm':  'text/html; charset=utf-8',
    '.css':  'text/css',
    '.js':   'application/javascript',
    '.mjs':  'application/javascript',
    '.json': 'application/json',
    '.svg':  'image/svg+xml',
    '.png':  'image/png',
    '.jpg':  'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.ico':  'image/x-icon',
    '.txt':  'text/plain; charset=utf-8',
    '.md':   'text/plain; charset=utf-8',
}


@method_decorator(xframe_options_exempt, name='dispatch')
class PreviewProxyView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, id, path=''):
        import os
        project = StudioProject.objects.get(id=id, user=request.user)

        # 1. If sandbox is running, proxy to it
        if project.sandbox_container_id:
            host = project.sandbox_container_id
            try:
                upstream = _rq.get(
                    f'http://{host}:3000/{path}',
                    timeout=5,
                    headers={'Accept': request.headers.get('Accept', '*/*')},
                    allow_redirects=True,
                )
                resp = HttpResponse(upstream.content, status=upstream.status_code)
                ct = upstream.headers.get('Content-Type')
                if ct:
                    resp['Content-Type'] = ct
                resp['X-Frame-Options'] = 'SAMEORIGIN'
                return resp
            except Exception:
                pass  # fall through to static serving

        # 2. Fallback: serve project files directly from DB (static HTML/CSS/JS)
        serve_path = path.strip('/') or 'index.html'
        file_obj = project.files.filter(path=serve_path).first()
        if not file_obj:
            # Try root-level index.html
            file_obj = project.files.filter(path__in=['index.html', 'public/index.html', 'src/index.html']).first()
        if not file_obj:
            return HttpResponse('<h1>Файл не найден</h1>', content_type='text/html; charset=utf-8', status=404)

        ext = os.path.splitext(serve_path)[1].lower()
        content_type = _MIME.get(ext, 'text/plain; charset=utf-8')
        body = file_obj.content
        if ext in ('.html', '.htm'):
            base_href = f'/api/v1/studio/projects/{id}/preview/'
            tag = f'<base href="{base_href}">'
            # Error capture hook: relays window.onerror + console.error to parent via postMessage
            err_hook = (
                '<script>(function(){'
                'function send(p){try{parent.postMessage('
                '{type:"studio-console-error",payload:p},"*");}catch(e){}}'
                'window.addEventListener("error",function(e){'
                'send({message:String(e.message||e.error||""),file:e.filename||"",'
                'line:e.lineno||0,stack:(e.error&&e.error.stack)||""});});'
                'var _oc=console.error;console.error=function(){'
                'send({message:Array.prototype.join.call(arguments," "),file:"",line:0,stack:""});'
                '_oc.apply(console,arguments);};'
                '})();</script>'
            )
            # TMA mock-SDK: inject window.Telegram.WebApp stub when STUDIO_V4_TMA is on
            tma_mock = ''
            if getattr(settings, 'STUDIO_V4_TMA', False):
                tma_mock = (
                    '<script>'
                    'window.Telegram={WebApp:{'
                    'ready:function(){},expand:function(){},'
                    'close:function(){},'
                    'colorScheme:"light",'
                    'themeParams:{},'
                    'initData:"",'
                    'initDataUnsafe:{user:{id:1,first_name:"Preview",username:"preview"}},'
                    'showAlert:function(m){alert(m);},'
                    'showConfirm:function(m,cb){cb(confirm(m));},'
                    'openInvoice:function(url,cb){alert("TMA payment mock: "+url);if(cb)cb("paid");},'
                    'MainButton:{setText:function(){},show:function(){},hide:function(){},'
                    'onClick:function(fn){this._fn=fn;},offClick:function(){}},'
                    'BackButton:{show:function(){},hide:function(){},'
                    'onClick:function(fn){this._fn=fn;},offClick:function(){}},'
                    'onEvent:function(){},offEvent:function(){},'
                    'sendData:function(d){console.log("TMA sendData:",d);}'
                    '}};'
                    '</script>'
                )
            inject = tag + err_hook + tma_mock
            if '<head>' in body:
                body = body.replace('<head>', f'<head>{inject}', 1)
            elif '<html>' in body:
                body = body.replace('<html>', f'<html><head>{inject}</head>', 1)
            else:
                body = inject + body
        resp = HttpResponse(body, content_type=content_type)
        resp['X-Frame-Options'] = 'SAMEORIGIN'
        return resp
