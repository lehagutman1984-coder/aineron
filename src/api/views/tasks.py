"""S2 — AI-Задачи: веб-зеркало /account/tasks/ (задачи общие для веба и бота)."""
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from telegram_bot.models import AITask, ai_task_limit


class AITaskSerializer(serializers.ModelSerializer):
    schedule_human = serializers.CharField(read_only=True)  # DRF вызывает метод модели
    network_name = serializers.CharField(read_only=True, source='network.name', default=None)

    class Meta:
        model = AITask
        fields = [
            'id', 'title', 'prompt', 'schedule_type', 'run_time', 'weekday',
            'cron', 'next_run_at', 'use_web_search', 'network', 'network_name',
            'is_active', 'paused_reason', 'last_run_at', 'runs_count',
            'max_runs', 'created_from', 'created_at', 'schedule_human',
        ]
        read_only_fields = [
            'id', 'next_run_at', 'paused_reason', 'last_run_at',
            'runs_count', 'created_from', 'created_at',
        ]


class AITaskListCreateView(APIView):
    """GET /v1/tasks/ — список задач; POST — создать."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        tasks = AITask.objects.filter(user=request.user).order_by('-is_active', '-created_at')
        return Response({
            'tasks': AITaskSerializer(tasks, many=True).data,
            'active_count': tasks.filter(is_active=True).count(),
            'limit': ai_task_limit(request.user),
        })

    def post(self, request):
        serializer = AITaskSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        active = AITask.objects.filter(user=request.user, is_active=True).count()
        limit = ai_task_limit(request.user)
        if active >= limit:
            return Response(
                {'error': f'Достигнут лимит активных задач по тарифу: {limit}'},
                status=status.HTTP_403_FORBIDDEN,
            )

        task = serializer.save(user=request.user, created_from='web')
        task.next_run_at = task.compute_next_run()
        task.save(update_fields=['next_run_at'])
        return Response(AITaskSerializer(task).data, status=status.HTTP_201_CREATED)


class AITaskDetailView(APIView):
    """PATCH /v1/tasks/<id>/ — изменить; DELETE — удалить."""
    permission_classes = [IsAuthenticated]

    def _get(self, request, pk):
        return AITask.objects.filter(user=request.user, pk=pk).first()

    def patch(self, request, pk):
        task = self._get(request, pk)
        if task is None:
            return Response({'error': 'not found'}, status=status.HTTP_404_NOT_FOUND)

        # Включение задачи — проверка лимита
        if request.data.get('is_active') and not task.is_active:
            active = AITask.objects.filter(user=request.user, is_active=True).count()
            if active >= ai_task_limit(request.user):
                return Response(
                    {'error': 'Достигнут лимит активных задач по тарифу'},
                    status=status.HTTP_403_FORBIDDEN,
                )

        serializer = AITaskSerializer(task, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        task = serializer.save()
        if 'is_active' in request.data:
            task.paused_reason = '' if task.is_active else 'user'
        if task.is_active and task.schedule_type != AITask.Schedule.ONCE:
            task.next_run_at = task.compute_next_run()
        task.save()
        return Response(AITaskSerializer(task).data)

    def delete(self, request, pk):
        task = self._get(request, pk)
        if task is None:
            return Response({'error': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        task.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AITaskRunNowView(APIView):
    """POST /v1/tasks/<id>/run/ — запустить сейчас (результат придёт в Telegram)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.utils import timezone
        task = AITask.objects.filter(user=request.user, pk=pk).first()
        if task is None:
            return Response({'error': 'not found'}, status=status.HTTP_404_NOT_FOUND)
        if not hasattr(request.user, 'telegram'):
            return Response(
                {'error': 'Для доставки результата привяжите Telegram в кабинете'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        from telegram_bot.tasks import execute_ai_task
        execute_ai_task.delay(task.pk, f'manual:{timezone.now().isoformat()}')
        return Response({'status': 'queued'})
