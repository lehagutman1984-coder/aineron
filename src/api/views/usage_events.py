"""
GET /v1/usage-events/ — unified analytics dashboard (staff only).
GET /v1/usage-events/summary/ — aggregate stats for the last 30 days.
"""
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from datetime import timedelta

from aitext.models import UsageEvent


class UsageEventListView(APIView):
    """Last 500 usage events — staff only."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        channel = request.query_params.get('channel')
        event_type = request.query_params.get('event_type')
        qs = UsageEvent.objects.select_related('user', 'network').order_by('-created_at')
        if channel:
            qs = qs.filter(channel=channel)
        if event_type:
            qs = qs.filter(event_type=event_type)
        events = qs[:500]
        return Response([
            {
                'id': e.id,
                'user': e.user.email if e.user else None,
                'channel': e.channel,
                'event_type': e.event_type,
                'network': e.network.name if e.network else None,
                'cost': e.cost,
                'meta': e.meta,
                'created_at': e.created_at.isoformat(),
            }
            for e in events
        ])


class UsageEventSummaryView(APIView):
    """Daily aggregates for last 30 days — staff only."""
    permission_classes = [IsAuthenticated, IsAdminUser]

    def get(self, request):
        since = timezone.now() - timedelta(days=30)
        qs = UsageEvent.objects.filter(created_at__gte=since)

        # By channel + event_type
        by_type = (
            qs.values('channel', 'event_type')
            .annotate(count=Count('id'), total_cost=Sum('cost'))
            .order_by('-count')
        )

        # Daily totals
        daily = (
            qs.annotate(date=TruncDate('created_at'))
            .values('date', 'channel')
            .annotate(count=Count('id'), total_cost=Sum('cost'))
            .order_by('date', 'channel')
        )

        # Top models
        top_models = (
            qs.exclude(network=None)
            .values('network__name', 'channel')
            .annotate(count=Count('id'), total_cost=Sum('cost'))
            .order_by('-count')[:20]
        )

        return Response({
            'period_days': 30,
            'total_events': qs.count(),
            'by_type': list(by_type),
            'daily': [
                {
                    'date': str(r['date']),
                    'channel': r['channel'],
                    'count': r['count'],
                    'total_cost': r['total_cost'] or 0,
                }
                for r in daily
            ],
            'top_models': list(top_models),
        })
