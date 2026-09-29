"""
2026-09-29: RelayHTTPBackend падал на письмах с subject через
django.utils.translation.gettext_lazy (ленивый прокси-объект, не str) —
requests.post(json=...) не может его сериализовать. Проявилось только на
aineron.net (реальный прогон через relay), потому что прямой SMTP-бэкенд
(aineron.ru) сам приводит subject к str при сборке email.message и скрывал
баг. Тест бьёт именно в этот сценарий, а не просто "subject есть".
"""
from unittest import mock

from django.core.mail import EmailMultiAlternatives
from django.test import TestCase, override_settings
from django.utils.translation import gettext_lazy as _

from core.mail_relay_backend import RelayHTTPBackend


def _message(subject='Тема', body='Текст', html=None):
    msg = EmailMultiAlternatives(subject=subject, body=body, from_email='a@a.ru', to=['b@b.ru'])
    if html:
        msg.attach_alternative(html, 'text/html')
    return msg


@override_settings(MAIL_RELAY_URL='https://aineron.ru/api/v1/internal/mail-relay/', MAIL_RELAY_SECRET='s3cr3t')
class RelayHTTPBackendTests(TestCase):
    def test_plain_str_subject_sends(self):
        backend = RelayHTTPBackend()
        with mock.patch('requests.post') as post:
            post.return_value = mock.Mock(status_code=200)
            sent = backend.send_messages([_message(subject='Обычная строка')])
        self.assertEqual(sent, 1)
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['subject'], 'Обычная строка')

    def test_lazy_translation_subject_serializes_correctly(self):
        """Регрессия: subject = gettext_lazy(...) не должен ронять релей."""
        backend = RelayHTTPBackend()
        msg = _message(subject=_('Пароль изменён'), body=_('Текст письма'))
        with mock.patch('requests.post') as post:
            post.return_value = mock.Mock(status_code=200)
            sent = backend.send_messages([msg])
        self.assertEqual(sent, 1)
        payload = post.call_args.kwargs['json']
        self.assertEqual(payload['subject'], 'Пароль изменён')
        self.assertIsInstance(payload['subject'], str)
        self.assertEqual(payload['text'], 'Текст письма')
        # Сама суть регрессии: mock.patch подменяет requests.post целиком, так что
        # реальный json.dumps() внутри requests не выполняется - проверяем его
        # отдельно и явно, иначе тест не поймал бы "Object of type __proxy__
        # is not JSON serializable" даже при откате фикса.
        import json
        json.dumps(payload)

    def test_missing_config_fails_open_without_relay_call(self):
        with override_settings(MAIL_RELAY_URL='', MAIL_RELAY_SECRET=''):
            backend = RelayHTTPBackend(fail_silently=True)
            with mock.patch('requests.post') as post:
                sent = backend.send_messages([_message()])
            post.assert_not_called()
        self.assertEqual(sent, 0)

    def test_relay_http_error_raises_when_not_fail_silently(self):
        backend = RelayHTTPBackend(fail_silently=False)
        with mock.patch('requests.post') as post:
            post.return_value = mock.Mock(status_code=500, text='boom')
            with self.assertRaises(RuntimeError):
                backend.send_messages([_message()])
