"""
2026-10-02 (аудит безопасности, LOW):
- GenerationUnshareView не ревокал share_slug - повторный share переиспользовал
  старый slug, старая, ранее разошедшаяся ссылка снова начинала работать.
- GenerationLikeView не был атомарным (read-then-write race) и не имел
  выделенного троттла.
"""
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from aitext.models import GeneratedImage

User = get_user_model()
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _gen(user, **kw):
    d = dict(user=user, image='x.png', media_type='image', message=None, prompt='test')
    d.update(kw)
    return GeneratedImage.objects.create(**d)


@override_settings(CACHES=LOCMEM)
class UnshareRevokesSlugTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='u', email='u@t.ru', password='x')
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_unshare_clears_slug_old_link_stops_working(self):
        gen = _gen(self.user)
        share_resp = self.client.post(f'/api/v1/generations/{gen.id}/share/')
        self.assertEqual(share_resp.status_code, 200)
        old_slug = share_resp.json()['share_slug']
        self.assertTrue(old_slug)

        # Публичная ссылка работает, пока расшарено.
        self.assertEqual(self.client.get(f'/api/v1/generations/{old_slug}/public/').status_code, 200)

        unshare_resp = self.client.post(f'/api/v1/generations/{gen.id}/unshare/')
        self.assertEqual(unshare_resp.status_code, 200)
        self.assertEqual(unshare_resp.json()['share_slug'], None)

        # Старая ссылка больше не работает ни напрямую,
        self.assertEqual(self.client.get(f'/api/v1/generations/{old_slug}/public/').status_code, 404)

        # ...и не оживает при повторном share - выдаётся НОВЫЙ slug.
        reshare_resp = self.client.post(f'/api/v1/generations/{gen.id}/share/')
        self.assertEqual(reshare_resp.status_code, 200)
        new_slug = reshare_resp.json()['share_slug']
        self.assertNotEqual(new_slug, old_slug)
        self.assertEqual(self.client.get(f'/api/v1/generations/{old_slug}/public/').status_code, 404)
        self.assertEqual(self.client.get(f'/api/v1/generations/{new_slug}/public/').status_code, 200)

    def test_unsharing_twice_does_not_crash_on_unique_constraint(self):
        """Регрессия на саму реализацию фикса: share_slug должен очищаться в
        None, а не '' - unique=True допускает много NULL, но не много ''."""
        gen1 = _gen(self.user)
        gen2 = _gen(self.user)
        self.client.post(f'/api/v1/generations/{gen1.id}/share/')
        self.client.post(f'/api/v1/generations/{gen2.id}/share/')

        r1 = self.client.post(f'/api/v1/generations/{gen1.id}/unshare/')
        r2 = self.client.post(f'/api/v1/generations/{gen2.id}/unshare/')
        self.assertEqual(r1.status_code, 200)
        self.assertEqual(r2.status_code, 200)  # не 500 IntegrityError на втором unshare


@override_settings(CACHES=LOCMEM)
class GenerationLikeTests(TestCase):
    def setUp(self):
        # Троттлинг живёт в кэше, не в БД - транзакционный rollback между
        # тестами его не чистит (тот же класс контаминации, что у
        # PromoRedemptionAntifraudTests). Сбрасываем явно на каждый тест,
        # иначе test_like_throttled_after_burst зависит от порядка запуска.
        from django.core.cache import cache
        cache.clear()
        self.owner = User.objects.create_user(username='owner', email='owner@t.ru', password='x')
        self.gen = _gen(self.owner, is_public=True, likes=0)
        self.client = APIClient()

    def test_anonymous_like_increments_atomically(self):
        resp = self.client.post(f'/api/v1/generations/{self.gen.id}/like/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['likes'], 1)
        self.gen.refresh_from_db()
        self.assertEqual(self.gen.likes, 1)

    def test_like_uses_f_expression_not_stale_read(self):
        """Два 'параллельных' вызова (симулируем последовательно, но без
        промежуточного refresh в вызывающем коде) не должны терять инкремент
        из-за read-then-write на закэшированном объекте."""
        from django.db.models import F
        # Имитация гонки: кто-то другой уже прибавил лайк в БД напрямую,
        # пока наш запрос "думал". F() в реализации должен это не потерять.
        GeneratedImage.objects.filter(id=self.gen.id).update(likes=F('likes') + 1)
        resp = self.client.post(f'/api/v1/generations/{self.gen.id}/like/')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['likes'], 2)  # 1 (гонка) + 1 (наш запрос), не 1

    def test_private_generation_cannot_be_liked(self):
        private_gen = _gen(self.owner, is_public=False)
        resp = self.client.post(f'/api/v1/generations/{private_gen.id}/like/')
        self.assertEqual(resp.status_code, 404)

    def test_like_throttled_after_burst(self):
        """generation_like scope = 20/min - 21-й запрос подряд должен получить 429.

        is_internal_service_request() (api/throttling.py) безусловно пропускает
        запросы БЕЗ X-Forwarded-For/X-Real-IP С приватного REMOTE_ADDR - ровно
        то, чем выглядит запрос тестового клиента Django (127.0.0.1, без
        заголовков). В реальном проде так выглядит только внутренний сервис
        (nginx всегда ставит оба заголовка внешнему трафику) - здесь явно
        подставляем их, как это сделал бы nginx, иначе throttle в тесте
        всегда бы молча байпасился (ложнозелёный тест)."""
        headers = {'HTTP_X_FORWARDED_FOR': '203.0.113.9', 'REMOTE_ADDR': '203.0.113.9'}
        for _ in range(20):
            resp = self.client.post(f'/api/v1/generations/{self.gen.id}/like/', **headers)
            self.assertEqual(resp.status_code, 200)
        resp = self.client.post(f'/api/v1/generations/{self.gen.id}/like/', **headers)
        self.assertEqual(resp.status_code, 429)
