"""
2026-09-29: у Beget нет self-service DKIM для этого типа аккаунта (проверено
в панели для aineron.ru и для другого домена на том же аккаунте — раздел
"Почта" даёт только создание ящика/пароль/пересылку, отдельного DKIM-тумблера
нет; стандартные селекторы default/beget/mail._domainkey тоже не резолвятся).
Без DKIM домен полагается только на SPF для DMARC-выравнивания — этого может
не хватать особо придирчивым фильтрам (mail.ru отклонял письма с похожей
конфигурацией кодом 550 spam message rejected на соседнем проекте).

Подписываем письма DKIM на уровне приложения (стандартная практика, когда
у почтового провайдера нет платформенной подписи) — не зависит от того, кто
физически отправляет письмо через smtp.beget.com (прямая отправка с .ru или
переслано через mail_relay с .net, см. api/views/mail_relay.py): оба пути
в итоге вызывают email.send() на ЭТОМ инстансе, использующем ЭТОТ backend.

Fail-open: если DKIM_* не настроены или подпись не удалась по любой причине —
письмо всё равно уходит, просто без подписи (как раньше). Отсутствие DKIM
никогда не должно блокировать реальную отправку.
"""
import logging

from django.conf import settings
from django.core.mail.backends.smtp import EmailBackend as SMTPEmailBackend

logger = logging.getLogger(__name__)


def _dkim_sign(raw_message: bytes) -> bytes:
    selector = getattr(settings, 'DKIM_SELECTOR', '')
    domain = getattr(settings, 'DKIM_DOMAIN', '')
    privkey = getattr(settings, 'DKIM_PRIVATE_KEY', '')
    if not (selector and domain and privkey):
        return raw_message
    try:
        import dkim
        sig = dkim.sign(
            raw_message,
            selector.encode(), domain.encode(), privkey.encode(),
            canonicalize=(b'relaxed', b'relaxed'),
        )
        return sig + raw_message
    except Exception as e:
        logger.warning(f"[dkim] подпись не применена (письмо всё равно уйдёт без неё): {e}")
        return raw_message


class DKIMSMTPBackend(SMTPEmailBackend):
    """SMTP-бэкенд Django + DKIM-Signature перед отправкой. Идентичен обычному
    SMTP-бэкенду Django (см. EmailBackend._send в django/core/mail/backends/smtp.py),
    если DKIM_* не заданы в settings (см. _dkim_sign выше) — единственная
    вставка: подпись сырых байт сообщения между message.as_bytes() и sendmail()."""

    def _send(self, email_message):
        import smtplib

        from django.core.mail.message import sanitize_address

        if not email_message.recipients():
            return False
        encoding = email_message.encoding or settings.DEFAULT_CHARSET
        from_email = sanitize_address(email_message.from_email, encoding)
        recipients = [
            sanitize_address(addr, encoding) for addr in email_message.recipients()
        ]
        message = email_message.message()
        try:
            # Django 4.2 (production): as_bytes() поддерживает linesep, шлём CRLF как в
            # оригинальном SMTP-бэкенде. На новых Django (локальный тест-venv может быть
            # другой версии) сигнатура as_bytes() иная — используем дефолт как фолбэк.
            raw_bytes = message.as_bytes(linesep='\r\n')
        except TypeError:
            raw_bytes = message.as_bytes()
        raw = _dkim_sign(raw_bytes)
        try:
            self.connection.sendmail(from_email, recipients, raw)
        except smtplib.SMTPException:
            if not self.fail_silently:
                raise
            return False
        return True
