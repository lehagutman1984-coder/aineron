"""U4 (UNIFIED_SUPREMACY) — Agent Mode на вебе.

POST /v1/agent/            {goal, project_id?} — запуск (цена по модели, см. core.feature_pricing)
GET  /v1/agent/quote/      — цена и модель ДО запуска
GET  /v1/agent/<id>/       — статус/шаги/отчёт (поллинг фронтендом)
GET  /v1/agent/            — последние запуски пользователя
"""
from django.conf import settings
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from telegram_bot.models import AgentRun
from api.error_messages import em
from api.permissions import IsEmailVerified


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
    permission_classes = [IsAuthenticated, IsEmailVerified]

    def get(self, request):
        runs = AgentRun.objects.filter(user=request.user)[:10]
        return Response({'runs': [_run_payload(r) for r in runs]})

    def post(self, request):
        from core.money import format_rub

        goal = (request.data.get('goal') or '').strip()
        if not goal:
            return Response({'error': em('agent_goal_required')}, status=400)

        # Модель и цена определяются один раз и передаются в задачу как есть
        # (core.feature_pricing; цена зависит от модели при FEATURE_MODEL_PRICING_ENABLED).
        from core.feature_pricing import resolve_feature
        from api.services.billing import top_up_url
        network, price = resolve_feature('agent', getattr(request.user, 'telegram', None))
        if network is None:
            return Response({'error': 'no models available'}, status=503)
        if not request.user.has_enough_kopecks(price):
            return Response(
                {'error': {
                    'message': em('agent_insufficient_funds', price=format_rub(price)),
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                    'required_kopecks': price,
                    'balance_kopecks': request.user.balance_kopecks,
                    'top_up_url': top_up_url(),
                }},
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
                return Response({'error': em('agent_project_not_found')}, status=404)

        run = AgentRun.objects.create(user=request.user, goal=goal[:2000],
                                      project=project)
        from telegram_bot.tasks import run_agent
        run_agent.delay(run.pk, price, network.pk)
        payload = _run_payload(run)
        payload['price_kopecks'] = price
        payload['model'] = network.name
        return Response(payload, status=201)


class AgentQuoteView(APIView):
    """GET /v1/agent/quote/ - цена и модель запуска агента ДО старта."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from core.feature_pricing import enabled, flat_price_kopecks, resolve_feature
        from core.money import format_rub

        network, price = resolve_feature('agent', getattr(request.user, 'telegram', None))
        return Response({
            'price_kopecks': price,
            'price_display': format_rub(price),
            'model': network.name if network else None,
            'model_dependent': enabled(),
            'base_price_kopecks': flat_price_kopecks('agent'),
            'balance_kopecks': request.user.balance_kopecks,
            'enough': request.user.has_enough_kopecks(price),
        })


class AgentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, run_id):
        run = AgentRun.objects.filter(pk=run_id, user=request.user).first()
        if run is None:
            return Response({'error': 'not found'}, status=404)
        return Response(_run_payload(run))
