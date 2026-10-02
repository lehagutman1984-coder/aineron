"""
2026-09-28: HTTP-ретранслятор почты .net -> .ru в обход блокировки исходящих
SMTP-портов у Hostkey (VPS 66.151.32.164). Серверная часть — MailRelayView
(этот файл); клиентская — core/mail_relay_backend.py::RelayHTTPBackend.

Django TestCase (SQLite): python manage.py test api.tests_mail_relay
"""
from unittest import mock

from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}
URL = '/api/v1/internal/mail-relay/'


@override_settings(
    MAIL_RELAY_SECRET='test-secret-123', CACHES=LOCMEM,
    # 2026-10-01: без явного override тест молча зависел от того, что в
    # окружении запуска MAIL_RELAY_ALLOWED_IPS пуст — на .ru в реальном .env
    # он НЕ пуст (там настоящий allowlist под IP .net-сервера), и запуск
    # этого файла внутри живого .ru-контейнера (а не изолированного CI)
    # заваливал все 8 тестов класса на постороннем IP-чеке, никак не
    # связанном с тем, что тесты реально проверяют.
    MAIL_RELAY_ALLOWED_IPS='',
)
class MailRelayViewTests(TestCase):
    def _post(self, payload, secret='test-secret-123'):
        client = APIClient()
        headers = {'HTTP_X_RELAY_SECRET': secret} if secret is not None else {}
        return client.post(URL, payload, format='json', **headers)

    def test_correct_secret_sends_email(self):
        resp = self._post({'to': ['user@example.com'], 'subject': 'Привет', 'text': 'тело письма'})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(mail.outbox), 1)
        sent = mail.outbox[0]
        self.assertEqual(sent.to, ['user@example.com'])
        self.assertEqual(sent.subject, 'Привет')
        self.assertEqual(sent.body, 'тело письма')

    def test_html_alternative_attached(self):
        resp = self._post({
            'to': ['user@example.com'], 'subject': 'S', 'text': 'plain',
            'html': '<b>rich</b>',
        })
        self.assertEqual(resp.status_code, 200)
        sent = mail.outbox[0]
        self.assertEqual(len(sent.alternatives), 1)
        self.assertEqual(sent.alternatives[0], ('<b>rich</b>', 'text/html'))

    def test_wrong_secret_rejected(self):
        resp = self._post({'to': ['a@b.com'], 'subject': 'x'}, secret='wrong')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_secret_header_rejected(self):
        resp = self._post({'to': ['a@b.com'], 'subject': 'x'}, secret=None)
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(MAIL_RELAY_SECRET='')
    def test_empty_configured_secret_never_matches(self):
        # Пустой секрет с обеих сторон не должен считаться совпадением —
        # иначе релей открыт всем, пока MAIL_RELAY_SECRET не настроен.
        resp = self._post({'to': ['a@b.com'], 'subject': 'x'}, secret='')
        self.assertEqual(resp.status_code, 403)

    def test_missing_to_rejected(self):
        resp = self._post({'subject': 'x', 'text': 'y'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_subject_rejected(self):
        resp = self._post({'to': ['a@b.com'], 'text': 'y'})
        self.assertEqual(resp.status_code, 400)

    def test_too_many_recipients_rejected(self):
        resp = self._post({'to': [f'u{i}@t.ru' for i in range(6)], 'subject': 'x'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_invalid_recipient_address_rejected(self):
        resp = self._post({'to': ['not-an-email'], 'subject': 'x'})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(len(mail.outbox), 0)

    def test_from_field_in_payload_is_ignored_no_spoofing(self):
        # Релей не должен позволять подменить отправителя произвольным from
        # из payload - иначе это открытый инструмент для спам/фишинг-рассылок
        # от чужого имени через доверенный домен aineron.ru.
        resp = self._post({
            'to': ['victim@example.com'], 'subject': 'x', 'text': 'y',
            'from': 'admin@bank-totally-legit.com',
        })
        self.assertEqual(resp.status_code, 200)
        sent = mail.outbox[0]
        self.assertNotEqual(sent.from_email, 'admin@bank-totally-legit.com')

    @mock.patch('api.views.mail_relay.EmailMultiAlternatives')
    def test_send_failure_returns_502(self, mock_email_cls):
        mock_email_cls.return_value.send.side_effect = RuntimeError('smtp down')
        resp = self._post({'to': ['a@b.com'], 'subject': 'x', 'text': 'y'})
        self.assertEqual(resp.status_code, 502)

    @override_settings(MAIL_RELAY_ALLOWED_IPS='66.151.32.164')
    def test_ip_allowlist_rejects_other_ips(self):
        client = APIClient()
        resp = client.post(
            URL, {'to': ['a@b.com'], 'subject': 'x'}, format='json',
            HTTP_X_RELAY_SECRET='test-secret-123', REMOTE_ADDR='1.2.3.4',
        )
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(len(mail.outbox), 0)

    @override_settings(MAIL_RELAY_ALLOWED_IPS='66.151.32.164')
    def test_ip_allowlist_accepts_x_real_ip_header(self):
        client = APIClient()
        resp = client.post(
            URL, {'to': ['a@b.com'], 'subject': 'x', 'text': 'y'}, format='json',
            HTTP_X_RELAY_SECRET='test-secret-123', HTTP_X_REAL_IP='66.151.32.164',
            REMOTE_ADDR='172.18.0.5',  # адрес nginx в докер-сети - не должен использоваться
        )
        self.assertEqual(resp.status_code, 200)

    def test_ip_allowlist_disabled_by_default(self):
        client = APIClient()
        resp = client.post(
            URL, {'to': ['a@b.com'], 'subject': 'x', 'text': 'y'}, format='json',
            HTTP_X_RELAY_SECRET='test-secret-123', REMOTE_ADDR='1.2.3.4',
        )
        self.assertEqual(resp.status_code, 200)


@override_settings(MAIL_RELAY_URL='https://aineron.ru/api/v1/internal/mail-relay/',
                    MAIL_RELAY_SECRET='shared-secret')
class RelayHTTPBackendTests(TestCase):
    def _message(self, html=None):
        msg = mail.EmailMultiAlternatives(
            subject='Тема', body='Текст', from_email='support@aineron.ru',
            to=['user@example.com'],
        )
        if html:
            msg.attach_alternative(html, 'text/html')
        return msg

    def test_empty_list_returns_zero_without_http_call(self):
        from core.mail_relay_backend import RelayHTTPBackend
        backend = RelayHTTPBackend()
        self.assertEqual(backend.send_messages([]), 0)

    @mock.patch('requests.post')
    def test_posts_payload_with_secret_header(self, mock_post):
        from core.mail_relay_backend import RelayHTTPBackend
        mock_post.return_value = mock.Mock(status_code=200, text='')
        backend = RelayHTTPBackend()
        sent = backend.send_messages([self._message(html='<p>hi</p>')])
        self.assertEqual(sent, 1)
        args, kwargs = mock_post.call_args
        self.assertEqual(args[0], 'https://aineron.ru/api/v1/internal/mail-relay/')
        self.assertEqual(kwargs['headers']['X-Relay-Secret'], 'shared-secret')
        self.assertEqual(kwargs['json']['to'], ['user@example.com'])
        self.assertEqual(kwargs['json']['subject'], 'Тема')
        self.assertEqual(kwargs['json']['html'], '<p>hi</p>')

    @mock.patch('requests.post')
    def test_non_200_raises_when_not_fail_silently(self, mock_post):
        from core.mail_relay_backend import RelayHTTPBackend
        mock_post.return_value = mock.Mock(status_code=403, text='forbidden')
        backend = RelayHTTPBackend(fail_silently=False)
        with self.assertRaises(RuntimeError):
            backend.send_messages([self._message()])

    @mock.patch('requests.post')
    def test_non_200_silent_when_fail_silently(self, mock_post):
        from core.mail_relay_backend import RelayHTTPBackend
        mock_post.return_value = mock.Mock(status_code=403, text='forbidden')
        backend = RelayHTTPBackend(fail_silently=True)
        sent = backend.send_messages([self._message()])
        self.assertEqual(sent, 0)

    @override_settings(MAIL_RELAY_URL='', MAIL_RELAY_SECRET='')
    def test_missing_config_raises_when_not_fail_silently(self):
        from core.mail_relay_backend import RelayHTTPBackend
        backend = RelayHTTPBackend(fail_silently=False)
        with self.assertRaises(RuntimeError):
            backend.send_messages([self._message()])
