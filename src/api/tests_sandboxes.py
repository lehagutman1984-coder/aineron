"""
Интеграционные тесты /api/v1/sandboxes/ — preview-service замокан.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from api.models import APIKey
from sandboxes.client import PreviewServiceError
from sandboxes.models import SandboxSession

User = get_user_model()

_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}

_CREATE_OK = {
    'session_id': 'x', 'e2b_id': 'e2b-internal', 'public_host': '3000-x.e2b.dev',
    'started_at': 1.0, 'expires_at': 301.0, 'claim_source': 'cold',
}


def make_user(email='api-sbx@test.ru', kopecks=100_000):
    user = User.objects.create(email=email, username=email.split('@')[0])
    # Новый пользователь получает стартовый грант сигналом — для детерминизма
    # тестов выставляем баланс точно.
    User.objects.filter(pk=user.pk).update(
        balance_kopecks=kopecks, pages_count=kopecks // 100,
    )
    user.refresh_from_db()
    return user


@override_settings(CACHES=_LOCMEM_CACHE, SANDBOX_API_ENABLED=True)
class SandboxAPITests(APITestCase):
    def setUp(self):
        self.user = make_user()
        self.client.force_authenticate(user=self.user)

    def _create(self, **overrides):
        body = {'template': 'base', 'size': 'standard', 'timeout_seconds': 300}
        body.update(overrides)
        with mock.patch('api.views.sandboxes.client.create', return_value=_CREATE_OK):
            return self.client.post('/api/v1/sandboxes/', body, format='json')

    # ── гейты ────────────────────────────────────────────────────────────────

    @override_settings(SANDBOX_API_ENABLED=False)
    def test_flag_off_returns_404(self):
        resp = self.client.get('/api/v1/sandboxes/')
        self.assertEqual(resp.status_code, 404)

    def test_shadow_banned_403(self):
        self.user.shadow_banned = True
        self.user.save(update_fields=['shadow_banned'])
        resp = self.client.get('/api/v1/sandboxes/')
        self.assertEqual(resp.status_code, 403)

    def test_api_key_without_scope_403(self):
        _, raw = APIKey.generate(self.user, 'no-scope')
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/v1/sandboxes/', HTTP_AUTHORIZATION=f'Bearer {raw}')
        self.assertEqual(resp.status_code, 403)
        self.assertEqual(resp.json()['error']['code'], 'missing_scope')

    def test_api_key_with_scope_ok(self):
        _, raw = APIKey.generate(self.user, 'scoped', scopes=['sandboxes'])
        self.client.force_authenticate(user=None)
        resp = self.client.get('/api/v1/sandboxes/', HTTP_AUTHORIZATION=f'Bearer {raw}')
        self.assertEqual(resp.status_code, 200)

    # ── создание ─────────────────────────────────────────────────────────────

    def test_create_happy_path(self):
        resp = self._create()
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertTrue(data['id'].startswith('sbx_'))
        self.assertEqual(data['state'], 'running')
        self.assertEqual(data['price_kopecks_per_min'], 100)
        session = SandboxSession.objects.get(pk=SandboxSession.parse_public_id(data['id']))
        self.assertEqual(session.reserved_kopecks, 500)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100_000 - 500)

    def test_create_insufficient_balance_402(self):
        poor = make_user(email='poor@test.ru', kopecks=100)
        self.client.force_authenticate(user=poor)
        resp = self._create()
        self.assertEqual(resp.status_code, 402)
        self.assertEqual(resp.json()['error']['code'], 'insufficient_balance')
        poor.refresh_from_db()
        self.assertEqual(poor.balance_kopecks, 100)  # ничего не списано

    def test_create_provisioning_error_refunds(self):
        with mock.patch('api.views.sandboxes.client.create',
                        side_effect=PreviewServiceError('boom', status=500)):
            resp = self.client.post('/api/v1/sandboxes/',
                                    {'template': 'base', 'timeout_seconds': 300}, format='json')
        self.assertEqual(resp.status_code, 502)
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100_000)  # полный возврат резерва
        self.assertEqual(
            SandboxSession.objects.filter(state=SandboxSession.State.FAILED).count(), 1,
        )

    def test_create_concurrency_limit_429(self):
        for i in range(3):
            SandboxSession.objects.create(
                user=self.user, template='base', size='small', ttl_seconds=60,
                state=SandboxSession.State.RUNNING,
            )
        resp = self._create()
        self.assertEqual(resp.status_code, 429)
        self.assertEqual(resp.json()['error']['code'], 'concurrency_limit')

    def test_create_validation_bad_template(self):
        resp = self._create(template='alpine')
        self.assertEqual(resp.status_code, 400)

    def test_create_validation_bad_env_key(self):
        resp = self._create(env={'foo-bar': 'x'})
        self.assertEqual(resp.status_code, 400)

    def test_create_ttl_above_max(self):
        resp = self._create(timeout_seconds=999999)
        self.assertEqual(resp.status_code, 400)

    def test_idempotency_key_returns_cached(self):
        with mock.patch('api.views.sandboxes.client.create', return_value=_CREATE_OK) as create_mock:
            r1 = self.client.post('/api/v1/sandboxes/', {'template': 'base'},
                                  format='json', HTTP_IDEMPOTENCY_KEY='k1')
            r2 = self.client.post('/api/v1/sandboxes/', {'template': 'base'},
                                  format='json', HTTP_IDEMPOTENCY_KEY='k1')
        self.assertEqual(r1.status_code, 201)
        self.assertEqual(r2.status_code, 201)
        self.assertEqual(r1.json()['id'], r2.json()['id'])
        self.assertEqual(create_mock.call_count, 1)
        self.assertEqual(SandboxSession.objects.count(), 1)

    # ── exec / files ─────────────────────────────────────────────────────────

    def _running_session(self):
        resp = self._create()
        return resp.json()['id']

    def test_exec_happy_path(self):
        sid = self._running_session()
        exec_result = {'exit_code': 0, 'stdout': '4\n', 'stderr': '',
                       'duration_ms': 12, 'truncated': False}
        with mock.patch('api.views.sandboxes.client.exec_', return_value=exec_result):
            resp = self.client.post(f'/api/v1/sandboxes/{sid}/exec/',
                                    {'code': 'print(2+2)'}, format='json')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['stdout'], '4\n')
        session = SandboxSession.objects.get(pk=SandboxSession.parse_public_id(sid))
        self.assertEqual(session.exec_count, 1)

    def test_exec_requires_command_or_code(self):
        sid = self._running_session()
        resp = self.client.post(f'/api/v1/sandboxes/{sid}/exec/', {}, format='json')
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(f'/api/v1/sandboxes/{sid}/exec/',
                                {'command': 'ls', 'code': 'x'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_exec_bad_cwd_traversal(self):
        sid = self._running_session()
        resp = self.client.post(f'/api/v1/sandboxes/{sid}/exec/',
                                {'command': 'ls', 'cwd': '/home/user/../../etc'}, format='json')
        self.assertEqual(resp.status_code, 400)

    def test_files_path_traversal_400(self):
        sid = self._running_session()
        resp = self.client.post(
            f'/api/v1/sandboxes/{sid}/files/',
            {'files': [{'path': '../../etc/passwd', 'content': 'x'}]}, format='json',
        )
        self.assertEqual(resp.status_code, 400)
        resp = self.client.post(
            f'/api/v1/sandboxes/{sid}/files/',
            {'files': [{'path': '/etc/passwd', 'content': 'x'}]}, format='json',
        )
        self.assertEqual(resp.status_code, 400)

    def test_files_read_bad_op(self):
        sid = self._running_session()
        resp = self.client.get(f'/api/v1/sandboxes/{sid}/files/',
                               {'path': '/home/user/a.txt', 'op': 'delete'})
        self.assertEqual(resp.status_code, 400)

    def test_foreign_session_404(self):
        sid = self._running_session()
        other = make_user(email='other@test.ru')
        self.client.force_authenticate(user=other)
        resp = self.client.get(f'/api/v1/sandboxes/{sid}/')
        self.assertEqual(resp.status_code, 404)

    # ── удаление ─────────────────────────────────────────────────────────────

    def test_delete_settles_billing(self):
        sid = self._running_session()
        with mock.patch('api.views.sandboxes.client.kill',
                        return_value={'ok': True, 'duration_seconds': 65}):
            resp = self.client.delete(f'/api/v1/sandboxes/{sid}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['charged_kopecks'], 200)  # ceil(65/60)=2 мин
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100_000 - 200)
        session = SandboxSession.objects.get(pk=SandboxSession.parse_public_id(sid))
        self.assertEqual(session.state, SandboxSession.State.STOPPED)

    def test_delete_twice_is_safe(self):
        sid = self._running_session()
        with mock.patch('api.views.sandboxes.client.kill',
                        return_value={'ok': True, 'duration_seconds': 30}):
            r1 = self.client.delete(f'/api/v1/sandboxes/{sid}/')
            r2 = self.client.delete(f'/api/v1/sandboxes/{sid}/')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)
        self.user.refresh_from_db()
        # Второй DELETE не менял баланс
        self.assertEqual(self.user.balance_kopecks, 100_000 - 100)

    def test_delete_when_service_unreachable_bills_full_ttl(self):
        sid = self._running_session()
        with mock.patch('api.views.sandboxes.client.kill',
                        side_effect=PreviewServiceError('down', status=0)):
            resp = self.client.delete(f'/api/v1/sandboxes/{sid}/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['charged_kopecks'], 500)  # полный TTL 5 мин

    # ── список ───────────────────────────────────────────────────────────────

    def test_list_active_only_by_default(self):
        sid = self._running_session()
        with mock.patch('api.views.sandboxes.client.kill',
                        return_value={'ok': True, 'duration_seconds': 30}):
            self.client.delete(f'/api/v1/sandboxes/{sid}/')
        self._create()
        resp = self.client.get('/api/v1/sandboxes/')
        self.assertEqual(len(resp.json()['data']), 1)
        resp = self.client.get('/api/v1/sandboxes/?all=1')
        self.assertEqual(len(resp.json()['data']), 2)
