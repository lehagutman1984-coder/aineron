import logging
import threading
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView, ListAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from teams.models import Organization, OrganizationMember, OrganizationInvite
from api.serializers.teams import (
    OrganizationSerializer, OrganizationMemberSerializer, OrganizationInviteSerializer,
)

logger = logging.getLogger(__name__)


def get_org_or_403(request, org_id):
    """Возвращает org; требует членства."""
    org = get_object_or_404(Organization, id=org_id)
    if not org.members.filter(user=request.user).exists():
        raise PermissionDenied('Вы не состоите в этой организации')
    return org


def get_org_admin_or_403(request, org_id):
    """Возвращает (org, member); требует роли owner/admin."""
    org = get_object_or_404(Organization, id=org_id)
    member = get_object_or_404(OrganizationMember, organization=org, user=request.user)
    if member.role not in (OrganizationMember.Role.OWNER, OrganizationMember.Role.ADMIN):
        raise PermissionDenied('Недостаточно прав')
    return org, member


class OrgListCreateView(ListCreateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    def get_queryset(self):
        return (
            Organization.objects
            .filter(members__user=self.request.user)
            .prefetch_related('members')
            .order_by('-created_at')
        )

    def create(self, request, *args, **kwargs):
        serializer = OrganizationSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        org = serializer.save(owner=request.user)
        OrganizationMember.objects.create(
            organization=org, user=request.user, role=OrganizationMember.Role.OWNER
        )
        return Response(
            OrganizationSerializer(org, context={'request': request}).data,
            status=201,
        )


class OrgDetailView(RetrieveUpdateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationSerializer

    def get_object(self):
        return get_org_or_403(self.request, self.kwargs['org_id'])

    def update(self, request, *args, **kwargs):
        org, _member = get_org_admin_or_403(request, self.kwargs['org_id'])
        partial = kwargs.pop('partial', False)
        serializer = OrganizationSerializer(
            org, data=request.data, partial=partial, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class OrgMemberListView(ListAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationMemberSerializer

    def get_queryset(self):
        get_org_or_403(self.request, self.kwargs['org_id'])
        return (
            OrganizationMember.objects
            .filter(organization_id=self.kwargs['org_id'])
            .select_related('user')
            .order_by('created_at')
        )


class OrgMemberDeleteView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, org_id, user_id):
        org, _requester = get_org_admin_or_403(request, org_id)
        target = get_object_or_404(OrganizationMember, organization=org, user_id=user_id)
        if target.role == OrganizationMember.Role.OWNER:
            return Response(
                {'error': {'message': 'Нельзя удалить владельца', 'type': 'invalid_request_error', 'code': None}},
                status=400,
            )
        target.delete()
        return Response(status=204)


class OrgInviteListCreateView(ListCreateAPIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]
    serializer_class = OrganizationInviteSerializer

    def get_queryset(self):
        get_org_or_403(self.request, self.kwargs['org_id'])
        return OrganizationInvite.objects.filter(
            organization_id=self.kwargs['org_id'],
            is_accepted=False,
        ).order_by('-created_at')

    def create(self, request, *args, **kwargs):
        org, _member = get_org_admin_or_403(request, self.kwargs['org_id'])
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response(
                {'error': {'message': 'Email обязателен', 'type': 'invalid_request_error', 'code': None}},
                status=400,
            )

        if org.members.filter(user__email=email).exists():
            return Response(
                {'error': {'message': 'Пользователь уже состоит в организации', 'type': 'invalid_request_error', 'code': None}},
                status=400,
            )

        invite, _created = OrganizationInvite.objects.get_or_create(
            organization=org, email=email, is_accepted=False,
        )
        # Refresh token/expiry for existing invites
        if not _created:
            invite.token = ''
            invite.expires_at = None
            invite.save()

        _send_invite_email_async(invite)
        return Response(OrganizationInviteSerializer(invite).data, status=201)


class InviteAcceptView(APIView):
    authentication_classes = [SessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, token):
        invite = get_object_or_404(OrganizationInvite, token=token, is_accepted=False)

        if invite.is_expired:
            return Response(
                {'error': {'message': 'Срок действия приглашения истёк', 'type': 'invalid_request_error', 'code': None}},
                status=400,
            )

        if invite.email != request.user.email:
            return Response(
                {'error': {'message': 'Приглашение выдано на другой email', 'type': 'authentication_error', 'code': None}},
                status=403,
            )

        OrganizationMember.objects.get_or_create(
            organization=invite.organization,
            user=request.user,
            defaults={'role': OrganizationMember.Role.MEMBER},
        )
        invite.is_accepted = True
        invite.save(update_fields=['is_accepted'])

        return Response({
            'ok': True,
            'organization': OrganizationSerializer(
                invite.organization, context={'request': request}
            ).data,
        })


class OrgTgTokenView(APIView):
    """POST /v1/orgs/<pk>/tg-token/ — generate Telegram group registration token."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        import secrets
        org, member = get_org_admin_or_403(request, pk)
        token = secrets.token_urlsafe(16)
        meta = org.meta or {}
        meta['tg_group_token'] = token
        org.meta = meta
        org.save(update_fields=['meta'])
        return Response({'token': token})


class OrgTgGroupsView(APIView):
    """GET /v1/orgs/<pk>/tg-groups/ — list connected Telegram groups."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        org = get_org_or_403(request, pk)
        from telegram_bot.models import TelegramGroup
        groups = TelegramGroup.objects.filter(organization=org).values(
            'id', 'group_id', 'group_title', 'enabled', 'created_at'
        )
        return Response(list(groups))

    def delete(self, request, pk):
        """DELETE /v1/orgs/<pk>/tg-groups/?group_id=<id> — unregister group."""
        org = get_org_or_403(request, pk)
        group_id = request.query_params.get('group_id')
        if group_id:
            from telegram_bot.models import TelegramGroup
            TelegramGroup.objects.filter(organization=org, group_id=group_id).delete()
        return Response(status=204)


def _send_invite_email_async(invite):
    """Отправляет письмо-приглашение в отдельном потоке."""
    from django.core.mail import send_mail

    site_url = getattr(settings, 'SITE_URL', 'https://aineron.ru')
    accept_url = f'{site_url}/account/invites/{invite.token}/'

    def send():
        try:
            send_mail(
                subject=f'Приглашение в организацию {invite.organization.name}',
                message=(
                    f'Вас пригласили в организацию «{invite.organization.name}» на aineron.ru.\n\n'
                    f'Примите приглашение: {accept_url}\n\n'
                    f'Ссылка действительна 7 дней.'
                ),
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@aineron.ru'),
                recipient_list=[invite.email],
                fail_silently=True,
            )
        except Exception as exc:
            logger.error(f'[INVITE] Ошибка отправки письма на {invite.email}: {exc}')

    t = threading.Thread(target=send, daemon=True)
    t.start()
