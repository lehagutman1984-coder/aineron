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
from django.db import IntegrityError, transaction
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import serializers as drf_serializers
from rest_framework import status

from aitext.models import UserMemory, ChatSummary
from aitext.memory import invalidate_memory_cache, scoped_content_key
from api.serializers.memory import UserMemorySerializer, ChatSummarySerializer
from api.error_messages import em


class MemoryListCreateView(ListCreateAPIView):
    """GET: список фактов. POST: создать вручную."""
    permission_classes = [IsAuthenticated]
    serializer_class = UserMemorySerializer

    def get_queryset(self):
        qs = UserMemory.objects.filter(user=self.request.user).select_related(
            'project', 'organization')
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)
        source = self.request.query_params.get('source')
        if source:
            qs = qs.filter(source=source)
        # U1: фильтр скоупа — global | project:<id> | all (по умолчанию all)
        scope = self.request.query_params.get('scope')
        if scope == 'global':
            qs = qs.filter(project__isnull=True, organization__isnull=True)
        elif scope and scope.startswith('project:'):
            try:
                qs = qs.filter(project_id=int(scope.split(':', 1)[1]))
            except ValueError:
                pass
        return qs.order_by('-is_pinned', '-created_at')

    def perform_create(self, serializer):
        # B12: content_key уникален per (user, scope) — при коллизии с уже
        # существующим фактом того же скоупа INSERT падает IntegrityError.
        # Раньше это улетало наружу необработанным 500; теперь — понятная 400.
        # atomic()-savepoint: без него IntegrityError оставляет внешнюю транзакцию
        # "отравленной" (TransactionManagementError на любой следующий запрос),
        # если вью вызвана внутри более широкого atomic-блока — например под тестами
        # (django.test.TestCase всегда оборачивает тест в atomic) или если проект
        # когда-нибудь включит ATOMIC_REQUESTS.
        try:
            with transaction.atomic():
                serializer.save(user=self.request.user, source='user')
        except IntegrityError:
            raise drf_serializers.ValidationError({'content': em('memory_duplicate_fact')})
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

        # B12: content и content_key должны меняться вместе, атомарно. Раньше
        # serializer.save() коммитил новый content первым, и если следующий шаг
        # (пересчёт content_key под новый текст) падал на коллизии — content
        # оставался обновлён, а content_key — от старого текста: факт и его
        # ключ дедупликации расходились. atomic() откатывает оба шага разом.
        try:
            with transaction.atomic():
                obj = serializer.save()
                if 'content' in data:
                    # Ключ должен учитывать текущий скоуп факта (project/organization),
                    # иначе редактирование текста молча ссорит его с фактом другого скоупа.
                    new_key = scoped_content_key(str(data['content']), obj.project_id, obj.organization_id)
                    if new_key and new_key != obj.content_key:
                        obj.content_key = new_key
                        obj.save(update_fields=['content_key'])
        except IntegrityError:
            raise drf_serializers.ValidationError({'content': em('memory_duplicate_fact')})

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
            return Response({'error': em('memory_text_required')}, status=400)

        # B12: единая (не подрезанная отдельно от остальных путей) схема ключа
        content_key = scoped_content_key(text)

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


class OrgMemoryView(APIView):
    """U1 — общая память организации.

    GET    /v1/orgs/<org_id>/memory/         — факты команды (любой член)
    POST   /v1/orgs/<org_id>/memory/         — создать (owner/admin)
    DELETE /v1/orgs/<org_id>/memory/?fact_id — удалить (owner/admin)
    """
    permission_classes = [IsAuthenticated]

    def _org_and_role(self, request, org_id):
        from teams.models import Organization, OrganizationMember
        org = Organization.objects.filter(pk=org_id).first()
        if org is None:
            return None, None
        if org.owner_id == request.user.id:
            return org, 'owner'
        member = OrganizationMember.objects.filter(
            organization=org, user=request.user).first()
        return (org, member.role) if member else (None, None)

    def _invalidate(self, org):
        from teams.models import OrganizationMember
        from aitext.memory import invalidate_org_memory_cache
        user_ids = list(OrganizationMember.objects.filter(organization=org)
                        .values_list('user_id', flat=True))
        user_ids.append(org.owner_id)
        invalidate_org_memory_cache(set(user_ids))

    def get(self, request, org_id):
        org, role = self._org_and_role(request, org_id)
        if org is None:
            return Response({'error': 'not found'}, status=404)
        facts = UserMemory.objects.filter(
            organization=org, is_active=True,
        ).order_by('-is_pinned', '-created_at')[:50]
        return Response({
            'facts': UserMemorySerializer(facts, many=True).data,
            'can_edit': role in ('owner', 'admin'),
        })

    def post(self, request, org_id):
        org, role = self._org_and_role(request, org_id)
        if org is None:
            return Response({'error': 'not found'}, status=404)
        if role not in ('owner', 'admin'):
            return Response({'error': em('memory_org_owner_admin_only')}, status=403)
        text = (request.data.get('content') or '').strip()
        if not text:
            return Response({'error': em('memory_content_required')}, status=400)

        # content_key уникален per-user — org-префикс (через scoped_content_key,
        # B12: та же схема, что и для project-скоупа) исключает конфликт
        # с личным фактом создателя с тем же текстом
        org_key = scoped_content_key(text, organization_id=org.pk)
        fact, _created = UserMemory.objects.update_or_create(
            user=request.user,
            content_key=org_key,
            defaults={
                'organization': org,
                'content': text[:500],
                'category': 'fact',
                'source': 'user',
                'is_active': True,
            },
        )
        self._invalidate(org)
        return Response(UserMemorySerializer(fact).data, status=201)

    def delete(self, request, org_id):
        org, role = self._org_and_role(request, org_id)
        if org is None:
            return Response({'error': 'not found'}, status=404)
        if role not in ('owner', 'admin'):
            return Response({'error': em('memory_org_owner_admin_only')}, status=403)
        fact_id = request.query_params.get('fact_id')
        if not fact_id:
            return Response({'error': em('memory_fact_id_required')}, status=400)
        deleted, _ = UserMemory.objects.filter(
            pk=fact_id, organization=org).delete()
        self._invalidate(org)
        return Response({'deleted': deleted})


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
            return Response({'error': em('memory_enabled_required')}, status=400)
        request.user.memory_enabled = bool(enabled)
        request.user.save(update_fields=['memory_enabled'])
        invalidate_memory_cache(request.user.id)  # B11: тоггл сбрасывает кэш
        return Response({'memory_enabled': request.user.memory_enabled})
