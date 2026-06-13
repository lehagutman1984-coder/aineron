from django.shortcuts import get_object_or_404
from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from teams.models import Organization, Invoice
from api.serializers.teams import InvoiceSerializer
from api.views.teams import get_org_admin_or_403


class InvoiceListCreateView(ListCreateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = InvoiceSerializer

    def get_queryset(self):
        org = get_object_or_404(Organization, id=self.kwargs['org_id'])
        if not org.members.filter(user=self.request.user).exists():
            raise PermissionDenied('Вы не состоите в этой организации')
        return Invoice.objects.filter(organization=org)

    def create(self, request, *args, **kwargs):
        org, _member = get_org_admin_or_403(request, self.kwargs['org_id'])

        try:
            amount = float(request.data.get('amount_rub') or 0)
            if amount <= 0:
                raise ValueError
        except (TypeError, ValueError):
            return Response(
                {'error': {'message': 'Укажите корректную сумму (руб.)', 'type': 'invalid_request_error', 'code': None}},
                status=400,
            )

        description = (request.data.get('description') or '').strip()
        invoice = Invoice.objects.create(
            organization=org,
            amount_rub=amount,
            description=description or f'Пополнение баланса организации {org.name}',
        )
        return Response(InvoiceSerializer(invoice).data, status=201)
