from datetime import timedelta
from django.db.models import Sum, Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response

from api.authentication import APIKeyAuthentication
from api.models import TokenUsage


class UsageStatsView(APIView):
    authentication_classes = [SessionAuthentication, APIKeyAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        try:
            days = min(int(request.query_params.get('days', 30)), 365)
        except (TypeError, ValueError):
            days = 30

        org_id = request.query_params.get('org_id')
        since = timezone.now() - timedelta(days=days)

        if org_id:
            from teams.models import Organization
            from rest_framework.exceptions import PermissionDenied
            try:
                org = Organization.objects.get(id=org_id)
            except Organization.DoesNotExist:
                return Response({'error': {'message': 'Организация не найдена'}}, status=404)
            if not org.members.filter(user=request.user).exists():
                raise PermissionDenied('Нет доступа к статистике организации')
            qs = TokenUsage.objects.filter(organization=org, created_at__gte=since)
        else:
            qs = TokenUsage.objects.filter(user=request.user, created_at__gte=since)

        by_day = list(
            qs.annotate(day=TruncDate('created_at'))
            .values('day')
            .annotate(
                total_tokens=Sum('total_tokens'),
                stars_charged=Sum('stars_charged'),
                cost_kopecks=Sum('cost_kopecks'),
                requests=Count('id'),
            )
            .order_by('day')
        )

        by_model = list(
            qs.exclude(network=None)
            .values('network__name', 'network__slug')
            .annotate(
                total_tokens=Sum('total_tokens'),
                stars_charged=Sum('stars_charged'),
                cost_kopecks=Sum('cost_kopecks'),
                requests=Count('id'),
            )
            .order_by('-total_tokens')[:20]
        )

        totals = qs.aggregate(
            total_tokens=Sum('total_tokens'),
            total_stars=Sum('stars_charged'),
            total_kopecks=Sum('cost_kopecks'),
            total_requests=Count('id'),
        )

        return Response({
            'period_days': days,
            'totals': {
                'total_tokens': totals['total_tokens'] or 0,
                'total_stars': totals['total_stars'] or 0,
                'total_kopecks': totals['total_kopecks'] or 0,
                'total_requests': totals['total_requests'] or 0,
            },
            'by_day': [
                {
                    'date': str(row['day']),
                    'total_tokens': row['total_tokens'] or 0,
                    'stars_charged': row['stars_charged'] or 0,
                    'cost_kopecks': row['cost_kopecks'] or 0,
                    'requests': row['requests'] or 0,
                }
                for row in by_day
            ],
            'by_model': [
                {
                    'model_name': row['network__name'],
                    'model_slug': row['network__slug'],
                    'total_tokens': row['total_tokens'] or 0,
                    'stars_charged': row['stars_charged'] or 0,
                    'cost_kopecks': row['cost_kopecks'] or 0,
                    'requests': row['requests'] or 0,
                }
                for row in by_model
            ],
        })
