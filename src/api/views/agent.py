"""U4 (UNIFIED_SUPREMACY) — Agent Mode на вебе.

POST /v1/agent/            {goal, project_id?} — запуск (цена AGENT_PRICE_KOPECKS)
GET  /v1/agent/<id>/       — статус/шаги/отчёт (поллинг фронтендом)
GET  /v1/agent/            — последние запуски пользователя
"""
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from telegram_bot.models import AgentRun


def _run_payload(run: AgentRun) -> dict:
    return {
        'id': run.pk,
        'goal': run.goal,
        'status': run.status,
        'steps': run.steps,
        'result_md': run.result_md if run.status == 'done' else '',
        'error': run.error,
        'project_id': run.project_id,
        'created_at': run.created_at,
        'finished_at': run.finished_at,
    }


class AgentStartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        runs = AgentRun.objects.filter(user=request.user)[:10]
        return Response({'runs': [_run_payload(r) for r in runs]})

    def post(self, request):
        from core.money import format_rub

        goal = (request.data.get('goal') or '').strip()
        if not goal:
            return Response({'error': 'goal обязателен'}, status=400)

        price = getattr(settings, 'AGENT_PRICE_KOPECKS', 500)
        if not request.user.has_enough_kopecks(price):
            return Response(
                {'error': f'Недостаточно средств: Agent Mode стоит {format_rub(price)}'},
                status=402,
            )

        project = None
        project_id = request.data.get('project_id')
        if project_id:
            from aitext.models import Project
            project = Project.objects.filter(pk=project_id, user=request.user).first()
            if project is None:
                from aitext.models import ProjectCollaborator
                collab = ProjectCollaborator.objects.filter(
                    project_id=project_id, user=request.user).select_related('project').first()
                project = collab.project if collab else None
            if project is None:
                return Response({'error': 'Проект не найден'}, status=404)

        run = AgentRun.objects.create(user=request.user, goal=goal[:2000],
                                      project=project)
        from telegram_bot.tasks import run_agent
        run_agent.delay(run.pk)
        return Response(_run_payload(run), status=201)


class AgentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, run_id):
        run = AgentRun.objects.filter(pk=run_id, user=request.user).first()
        if run is None:
            return Response({'error': 'not found'}, status=404)
        return Response(_run_payload(run))
