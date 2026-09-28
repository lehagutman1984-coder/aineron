"""
2026-09-28: aineron.net (Hostkey) блокирует все исходящие SMTP-порты
(25/465/587) даже к внешним хостам (Beget, Gmail) — политика провайдера,
не чинится на уровне приложения. Пересылает письма на aineron.ru по HTTPS
(443 не блокируется), где api/views/mail_relay.py реально отправляет их
через рабочий Beget SMTP того инстанса.

Используется только когда settings.MAIL_RELAY_URL задан (.net); на .ru
он пуст, и Django продолжает работать штатным SMTP-бэкендом без изменений —
этот файл на .ru просто не импортируется.

Django-контракт EmailBackend.send_messages(): вызывающий код
(EmailMessage.send(), django.core.mail.send_mail и т.п.) не различает
частичную/полную отправку — возвращаемое число используется только для
count-based веток кода (email_service.py эту cifra не проверяет, полагается
на исключение при fail_silently=False). Поэтому при ошибке хотя бы одного
письма с fail_silently=False бросаем исключение, как это сделал бы обычный
SMTP-бэкенд при обрыве соединения.
"""
import logging

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class RelayHTTPBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        import requests

        url = getattr(settings, 'MAIL_RELAY_URL', '')
        secret = getattr(settings, 'MAIL_RELAY_SECRET', '')
        if not url or not secret:
            logger.error('[mail_relay] MAIL_RELAY_URL/MAIL_RELAY_SECRET не заданы — письма не отправлены')
            if not self.fail_silently:
                raise RuntimeError('MAIL_RELAY_URL/MAIL_RELAY_SECRET не настроены')
            return 0

        sent = 0
        for message in email_messages:
            try:
                html_body = ''
                for content, mimetype in getattr(message, 'alternatives', None) or []:
                    if mimetype == 'text/html':
                        html_body = content
                        break

                payload = {
                    'to': list(message.to),
                    'subject': message.subject,
                    'text': message.body,
                    'html': html_body,
                }
                resp = requests.post(
                    url, json=payload, timeout=15,
                    headers={'X-Relay-Secret': secret},
                )
                if resp.status_code == 200:
                    sent += 1
                else:
                    logger.error(f'[mail_relay] релей вернул {resp.status_code}: {resp.text[:300]}')
                    if not self.fail_silently:
                        raise RuntimeError(f'mail relay HTTP {resp.status_code}')
            except Exception as e:
                logger.error(f'[mail_relay] ошибка отправки через релей: {e}')
                if not self.fail_silently:
                    raise
        return sent
