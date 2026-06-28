"""
DRF views для Persistent Memory.

GET    /api/v1/memory/               — список фактов пользователя
POST   /api/v1/memory/               — создать факт вручную
PATCH  /api/v1/memory/<id>/          — обновить (is_active, is_pinned, content)
DELETE /api/v1/memory/<id>/          — удалить факт
POST   /api/v1/memory/clear/         — удалить все авто-факты (source=auto)
GET    /api/v1/memory/summaries/     — список ChatSummary (readonly)
PATCH  /api/v1/memory/settings/      — toggle memory_enabled на пользователе
"""
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from aitext.models import UserMemory, ChatSummary
from aitext.memory import invalidate_memory_cache
from api.serializers.memory import UserMemorySerializer, ChatSummarySerializer


class MemoryListCreateView(ListCreateAPIView):
    """GET: список фактов. POST: создать вручную."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserMemorySerializer

    def get_queryset(self):
        qs = UserMemory.objects.filter(user=self.request.user)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        source = self.request.query_params.get('source')
        if source:
            qs = qs.filter(source=source)
        return qs.order_by('-is_pinned', '-created_at')

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, source='user')
        invalidate_memory_cache(self.request.user.id)  # B11: сбрасываем кэш


class MemoryDetailView(RetrieveUpdateDestroyAPIView):
    """PATCH/DELETE конкретного факта."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserMemorySerializer
    http_method_names = ['patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return UserMemory.objects.filter(user=self.request.user)

    def update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        allowed = {'content', 'is_active', 'is_pinned', 'category'}
        data = {k: v for k, v in request.data.items() if k in allowed}
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        obj = serializer.save()
        if 'content' in data:
            from aitext.memory import normalize_fact
            new_key = normalize_fact(str(data['content']))
            if new_key:
                obj.content_key = new_key
                obj.save(update_fields=['content_key'])
        invalidate_memory_cache(request.user.id)  # B11: сбрасываем кэш
        return Response(serializer.data)

    def perform_destroy(self, instance):
        instance.delete()
        invalidate_memory_cache(self.request.user.id)  # B11: сбрасываем кэш


class MemoryClearView(APIView):
    """POST /memory/clear/ — удалить все авто-извлечённые факты."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        deleted, _ = UserMemory.objects.filter(
            user=request.user, source='auto'
        ).delete()
        invalidate_memory_cache(request.user.id)  # B11
        return Response({'deleted': deleted})


class MemorySummariesView(APIView):
    """GET /memory/summaries/ — список ChatSummary (readonly)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        summaries = (
            ChatSummary.objects
            .filter(chat__user=request.user)
            .select_related('chat', 'chat__network')
            .order_by('-updated_at')[:20]
        )
        return Response(ChatSummarySerializer(summaries, many=True).data)


class QuickSaveFactView(APIView):
    """POST /memory/quick-save/ — Sprint 4: сохранить факт одним кликом из чата."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        text = (request.data.get('text') or '').strip()
        if not text:
            return Response({'error': 'text обязателен'}, status=400)

        from aitext.memory import normalize_fact
        content_key = normalize_fact(text)[:200]

        fact, created = UserMemory.objects.update_or_create(
            user=request.user,
            content_key=content_key,
            defaults={
                'content': text[:500],
                'category': 'fact',
                'source': 'user',
                'is_active': True,
            },
        )
        invalidate_memory_cache(request.user.id)
        return Response({'id': fact.id, 'content': fact.content, 'created': created})


class MemoryToastView(APIView):
    """GET /memory/toast/ — Sprint 4: one-shot toast data after extract_memory_facts.

    Returns and immediately clears the Redis key so the toast shows once.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        import json
        from django.core.cache import cache
        key = f"memory:toast:{request.user.id}"
        raw = cache.get(key)
        if not raw:
            return Response({'count': 0, 'facts': []})
        cache.delete(key)
        try:
            data = json.loads(raw)
        except Exception:
            data = {'count': 0, 'facts': []}
        return Response(data)


class MemorySettingsView(APIView):
    """PATCH /memory/settings/ — включить/выключить глобальную память."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            'memory_enabled': getattr(request.user, 'memory_enabled', True),
            'fact_count': UserMemory.objects.filter(
                user=request.user, is_active=True
            ).count(),
        })

    def patch(self, request):
        enabled = request.data.get('memory_enabled')
        if enabled is None:
            return Response({'error': 'memory_enabled обязателен'}, status=400)
        request.user.memory_enabled = bool(enabled)
        request.user.save(update_fields=['memory_enabled'])
        invalidate_memory_cache(request.user.id)  # B11: тоггл сбрасывает кэш
        return Response({'memory_enabled': request.user.memory_enabled})
