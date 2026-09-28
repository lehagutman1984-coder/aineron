"""
2026-09-28: aineron.net (Hostkey, VPS 66.151.32.164) блокирует все исходящие
SMTP-порты (25/465/587), даже к внешним хостам (Beget, Gmail) — политика
провайдера, не чинится на уровне приложения. .net шлёт письма сюда по HTTPS
(443 не блокируется, core/mail_relay_backend.py), aineron.ru реально
отправляет их через свой рабочий Beget SMTP.

Защищено общим секретом (MAIL_RELAY_SECRET) в заголовке, НЕ пользовательской
аутентификацией (JWT/APIKey) — это service-to-service вызов между двумя
своими инстансами одного проекта, не запрос от конечного пользователя.
authentication_classes/permission_classes намеренно пустые: секрет — сам
по себе полный контроль доступа, IsAuthenticated тут ни при чём.
"""
import hmac
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from rest_framework.response import Response
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

MAX_RECIPIENTS_PER_REQUEST = 5


class MailRelayThrottle(SimpleRateThrottle):
    """Общий лимит на ВСЕ запросы к релею (не per-IP/per-user) — трафик тут
    может быть только от .net, второго легитимного источника нет. Ставка —
    REST_FRAMEWORK.DEFAULT_THROTTLE_RATES['mail_relay'] в settings.py."""
    scope = 'mail_relay'

    def get_cache_key(self, request, view):
        return 'mail_relay_throttle'


def _client_ip(request) -> str:
    """nginx.conf ставит X-Real-IP = $remote_addr (реальный клиент) на всех
    проксируемых location — REMOTE_ADDR с точки зрения Django был бы адресом
    самого nginx/докер-сети, не настоящего клиента."""
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '')


class MailRelayView(APIView):
    authentication_classes = []
    permission_classes = []
    throttle_classes = [MailRelayThrottle]

    def post(self, request):
        # 2026-09-28 (доп. защита): второй независимый барьер поверх секрета —
        # список разрешённых IP (MAIL_RELAY_ALLOWED_IPS, через запятую). Пусто
        # по умолчанию = проверка выключена (fail-open на ЭТОЙ конкретной
        # проверке, чтобы опечатка в конфиге не заблокировала легитимный
        # трафик) — секрет остаётся обязательным барьером в любом случае.
        allowed_ips = [ip.strip() for ip in getattr(settings, 'MAIL_RELAY_ALLOWED_IPS', '').split(',') if ip.strip()]
        if allowed_ips:
            client_ip = _client_ip(request)
            if client_ip not in allowed_ips:
                logger.warning(f'[mail_relay] отклонён запрос с недопустимого IP={client_ip}')
                return Response({'error': 'forbidden'}, status=403)

        secret = getattr(settings, 'MAIL_RELAY_SECRET', '')
        provided = request.headers.get('X-Relay-Secret', '')
        # Пустой секрет с обеих сторон не должен считаться совпадением —
        # иначе релей открыт всем, пока MAIL_RELAY_SECRET не настроен.
        if not secret or not provided or not hmac.compare_digest(secret, provided):
            logger.warning(f'[mail_relay] отклонён запрос с неверным секретом, IP={request.META.get("REMOTE_ADDR")}')
            return Response({'error': 'forbidden'}, status=403)

        data = request.data if isinstance(request.data, dict) else {}
        to = data.get('to') or []
        subject = (data.get('subject') or '')[:200]
        text = data.get('text') or ''
        html = data.get('html') or ''

        if not isinstance(to, list) or not to or not subject:
            return Response({'error': 'invalid payload: to/subject required'}, status=400)
        if len(to) > MAX_RECIPIENTS_PER_REQUEST:
            return Response({'error': 'too many recipients'}, status=400)
        if not all(isinstance(addr, str) and '@' in addr for addr in to):
            return Response({'error': 'invalid recipient address'}, status=400)

        try:
            # from_email ВСЕГДА локальный EMAIL_HOST_USER этого инстанса —
            # payload намеренно не может задать from, иначе релей превращается
            # в открытый инструмент подмены отправителя (email spoofing).
            email = EmailMultiAlternatives(
                subject=subject, body=text,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', settings.EMAIL_HOST_USER),
                to=to,
            )
            if html:
                email.attach_alternative(html, 'text/html')
            email.send(fail_silently=False)
            logger.info(f'[mail_relay] переслано для .net: to={to}, subject={subject[:50]!r}')
            return Response({'status': 'sent'})
        except Exception as e:
            logger.error(f'[mail_relay] ошибка отправки: {e}', exc_info=True)
            return Response({'error': 'send_failed'}, status=502)
