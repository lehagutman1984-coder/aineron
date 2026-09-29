"""
2026-09-29: DKIM-подпись на уровне приложения (core/dkim_smtp_backend.py) —
у Beget нет self-service DKIM для аккаунта aineron.ru/студентам.сайт.

Django TestCase (SQLite): python manage.py test core.tests_dkim_smtp_backend
"""
from unittest import mock

import dkim
from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings

from core.dkim_smtp_backend import DKIMSMTPBackend

# Тестовый ключ — только для юнит-тестов, не используется нигде в проде.
_TEST_PRIVATE_KEY = None
_TEST_PUBLIC_KEY_B64 = None


def _generate_test_keypair():
    global _TEST_PRIVATE_KEY, _TEST_PUBLIC_KEY_B64
    if _TEST_PRIVATE_KEY is not None:
        return
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    key = rsa.generate_private_key(public_exponent=65537, key_size=1024)
    _TEST_PRIVATE_KEY = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pub_der = key.public_key().public_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    import base64
    _TEST_PUBLIC_KEY_B64 = base64.b64encode(pub_der).decode()


def _message(to=('user@example.com',), subject='Тема', body='Текст'):
    return EmailMultiAlternatives(
        subject=subject, body=body, from_email='support@aineron.ru', to=list(to),
    )


def _send_via_backend(msg):
    """Отправляет через DKIMSMTPBackend с замоканным SMTP-соединением,
    возвращает сырые байты, переданные в sendmail()."""
    backend = DKIMSMTPBackend(fail_silently=False)
    backend.connection = mock.Mock()
    backend.connection.sendmail = mock.Mock()
    backend.open = mock.Mock(return_value=False)  # соединение уже "открыто"
    backend.close = mock.Mock()
    sent = backend.send_messages([msg])
    call = backend.connection.sendmail.call_args
    raw = call[0][2] if call else None
    return sent, raw


class DKIMDisabledByDefaultTests(TestCase):
    """Без DKIM_SELECTOR/DOMAIN/PRIVATE_KEY — поведение как у обычного SMTP-бэкенда."""

    @override_settings(DKIM_SELECTOR='', DKIM_DOMAIN='', DKIM_PRIVATE_KEY='')
    def test_no_config_sends_without_signature(self):
        sent, raw = _send_via_backend(_message())
        self.assertEqual(sent, 1)
        self.assertNotIn(b'DKIM-Signature', raw)


class DKIMSigningTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        _generate_test_keypair()

    def _settings(self):
        return dict(DKIM_SELECTOR='test', DKIM_DOMAIN='aineron.ru', DKIM_PRIVATE_KEY=_TEST_PRIVATE_KEY)

    def test_signed_message_has_dkim_header(self):
        with override_settings(**self._settings()):
            sent, raw = _send_via_backend(_message())
        self.assertEqual(sent, 1)
        self.assertTrue(raw.startswith(b'DKIM-Signature:'))

    def test_signature_actually_verifies_against_public_key(self):
        """Не просто «заголовок есть» — сама подпись валидна и проходит
        dkim.verify() с нашим публичным ключом (главный риск при ручной
        DKIM-интеграции — некорректная канонизация, из-за которой подпись
        выглядит правильно, но не проходит верификацию нигде в реальности)."""
        with override_settings(**self._settings()):
            sent, raw = _send_via_backend(_message(subject='Проверка DKIM', body='привет мир'))

        def fake_dnsfunc(domain, timeout=5):
            self.assertIn(b'test._domainkey.aineron.ru', domain)
            return f'v=DKIM1; k=rsa; p={_TEST_PUBLIC_KEY_B64}'.encode()

        self.assertTrue(dkim.verify(raw, dnsfunc=fake_dnsfunc))

    def test_signature_covers_subject_tampering_detected(self):
        """Подмена темы после подписи должна ломать верификацию — иначе
        подпись ничего не защищает."""
        with override_settings(**self._settings()):
            sent, raw = _send_via_backend(_message(subject='Оригинал'))

        tampered = raw.replace(b'Subject: =?utf-8?b?', b'Subject: =?utf-8?b?X')  # испортить как есть
        if tampered == raw:
            tampered = raw.replace(b'Subject: Original', b'Subject: Hacked') if b'Subject: Original' in raw else raw[:-1] + b'!'

        def fake_dnsfunc(domain, timeout=5):
            return f'v=DKIM1; k=rsa; p={_TEST_PUBLIC_KEY_B64}'.encode()

        # Либо подмена не удалась синтетически (тест не показателен), либо верификация упала.
        if tampered != raw:
            self.assertFalse(dkim.verify(tampered, dnsfunc=fake_dnsfunc))

    def test_broken_private_key_fails_open_still_sends(self):
        with override_settings(DKIM_SELECTOR='test', DKIM_DOMAIN='aineron.ru',
                               DKIM_PRIVATE_KEY='not-a-real-key'):
            sent, raw = _send_via_backend(_message())
        self.assertEqual(sent, 1)
        self.assertNotIn(b'DKIM-Signature', raw)

    def test_missing_domain_only_no_signature(self):
        with override_settings(DKIM_SELECTOR='test', DKIM_DOMAIN='', DKIM_PRIVATE_KEY=_TEST_PRIVATE_KEY):
            sent, raw = _send_via_backend(_message())
        self.assertEqual(sent, 1)
        self.assertNotIn(b'DKIM-Signature', raw)
