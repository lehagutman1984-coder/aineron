"""
GET /api/v1/audit/ — журнал аудита для пользователя или организации.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from drf_spectacular.utils import extend_schema

from api.models import AuditLog
from teams.models import OrganizationMember


class AuditLogListView(APIView):
    """GET /api/v1/audit/"""
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='Журнал аудита',
        tags=['Audit'],
        description='Возвращает последние 200 записей аудита для пользователя. '
                    'Параметр ?org_id=N возвращает журнал организации (только admins/owner).',
    )
    def get(self, request):
        org_id = request.query_params.get('org_id')

        if org_id:
            # Проверяем, что пользователь — admin/owner организации
            try:
                member = OrganizationMember.objects.get(
                    organization_id=org_id,
                    user=request.user,
                    role__in=[OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN],
                )
            except OrganizationMember.DoesNotExist:
                return Response({'error': {'message': 'Access denied', 'type': 'forbidden', 'code': 'forbidden'}}, status=403)
            qs = AuditLog.objects.filter(organization_id=org_id)
        else:
            qs = AuditLog.objects.filter(user=request.user)

        logs = qs.order_by('-created_at').select_related('user')[:200]
        data = [
            {
                'id': log.pk,
                'action': log.action,
                'resource_type': log.resource_type,
                'resource_id': log.resource_id,
                'metadata': log.metadata,
                'ip_address': log.ip_address,
                'user_email': log.user.email if log.user else None,
                'created_at': log.created_at.isoformat(),
            }
            for log in logs
        ]
        return Response(data)
