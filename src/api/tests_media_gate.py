"""
Part C (STATUS_AND_BACKLOG_PLAN_2026-09-25.md, ITEM 1 audit, 2026-09-28): единый
предикат can_generate_media()/is_unpaid_free_user(), включая Stars-исправление, и
закрытые пробелы в местах, где медиа-гейта раньше не было вовсе (images.py
generations, compare.py, RegenerateView для fal-ai, легаси aitext/views.py) плюс
Celery-бэкстоп в generate_ai_response.
"""
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from aitext.models import Category, Chat, Message, NeuralNetwork
from users.models import BalanceTransaction, PaymentHistory, Tariff

User = get_user_model()
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}


def _network(provider='fal-ai', cost=500, **kw):
    cat, _ = Category.objects.get_or_create(name='M', defaults={'slug': 'm'})
    d = dict(name='Img', slug=f'img-{provider}-{cost}', model_name=f'img-{cost}', category=cat,
             cost_per_message=5, cost_kopecks=cost, provider=provider, is_active=True)
    d.update(kw)
    return NeuralNetwork.objects.create(**d)


def _trial(balance=100000, email='trial@t.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.tariff = Tariff.get_default_tariff()
    u.set_kopecks(balance)
    u.save(update_fields=['tariff', 'email_verified'])
    return u


def _paying(balance=100000, email='paid@t.ru'):
    u = _trial(balance, email)
    PaymentHistory.objects.create(user=u, payment_type='pages', amount=100, status='success')
    return u


def _stars_payer(balance=100000, email='stars@t.ru'):
    u = _trial(balance, email)
    u.add_kopecks(500, type='xtr', reference='stars:test1')
    return u


def _client(user):
    c = APIClient()
    c.force_authenticate(user)
    return c


class PredicateTests(TestCase):
    def test_trial_user_is_unpaid_and_cannot_generate_media(self):
        u = _trial()
        self.assertTrue(u.is_unpaid_free_user())
        self.assertFalse(u.can_generate_media())

    def test_robokassa_payer_is_paid(self):
        u = _paying()
        self.assertFalse(u.is_unpaid_free_user())
        self.assertTrue(u.can_generate_media())

    def test_stars_xtr_topup_counts_as_real_payment(self):
        """Раньше has_made_real_payment видел только PaymentHistory(status='success') —
        обычный топ-ап Telegram Stars (add_kopecks(type='xtr')) его не создаёт, и
        реальный плательщик через Stars (штатный способ на .net) засчитывался бесплатным."""
        u = _stars_payer()
        self.assertTrue(u.has_made_real_payment())
        self.assertFalse(u.is_unpaid_free_user())
        self.assertTrue(u.can_generate_media())

    def test_promo_credit_alone_does_not_count_as_real_payment(self):
        u = _trial()
        u.add_kopecks(500, type='promo', reference='promo:test1')
        self.assertFalse(u.has_made_real_payment())
        self.assertFalse(u.can_generate_media())


@override_settings(CACHES=LOCMEM)
class ImagesEndpointGateTests(TestCase):
    def test_trial_user_blocked_before_upstream_call(self):
        _network()
        u = _trial()
        with mock.patch('api.views.images.get_laozhang_image_client') as client:
            r = _client(u).post('/api/v1/images/generations', {'prompt': 'cat'}, format='json')
        self.assertEqual(r.status_code, 402)
        client.assert_not_called()

    def test_paying_user_passes_the_gate(self):
        net = _network()
        u = _paying()
        fake = mock.MagicMock()
        fake.images.generate.return_value = mock.MagicMock(data=[mock.MagicMock(url='http://x/y.png')])
        with mock.patch('api.views.images.get_laozhang_image_client', return_value=fake), \
                mock.patch('api.views.images.save_media_from_url', return_value=None):
            r = _client(u).post('/api/v1/images/generations', {'prompt': 'cat', 'model': net.model_name}, format='json')
        self.assertEqual(r.status_code, 200)


@override_settings(CACHES=LOCMEM)
class CompareGateTests(TestCase):
    def test_trial_user_blocked_when_any_selected_model_is_media(self):
        text_net = _network(provider='openrouter', cost=100)
        media_net = _network(provider='fal-ai', cost=500)
        u = _trial()
        r = _client(u).post('/api/v1/compare/', {
            'message': 'hi', 'network_slugs': [text_net.slug, media_net.slug],
        }, format='json')
        self.assertEqual(r.status_code, 402)
        self.assertEqual(Chat.objects.count(), 0)

    def test_text_only_compare_not_affected_by_media_gate(self):
        a = _network(provider='openrouter', cost=100)
        b = _network(provider='openrouter', cost=100, slug='img-openrouter-101', model_name='m2')
        u = _trial()
        with mock.patch('api.views.compare.generate_ai_response'):
            r = _client(u).post('/api/v1/compare/', {
                'message': 'hi', 'network_slugs': [a.slug, b.slug],
            }, format='json')
        self.assertEqual(r.status_code, 201)


@override_settings(CACHES=LOCMEM)
class RegenerateGateTests(TestCase):
    def test_trial_user_blocked_for_fal_ai_regenerate(self):
        net = _network(provider='fal-ai')
        u = _trial()
        chat = Chat.objects.create(user=u, network=net, title='c')
        Message.objects.create(chat=chat, role='user', content='hi', status='completed')
        Message.objects.create(chat=chat, role='assistant', content='pic', status='completed')
        r = _client(u).post(f'/api/v1/chats/{chat.id}/regenerate/', {}, format='json')
        self.assertEqual(r.status_code, 402)


@override_settings(CACHES=LOCMEM)
class LegacyViewsGateTests(TestCase):
    def test_create_chat_blocks_trial_user_for_media_network(self):
        net = _network(provider='fal-ai')
        u = _trial()
        c = self.client
        c.force_login(u)
        r = c.post('/aitext/api/create-chat/', {'network_slug': net.slug, 'message': 'hi'},
                   content_type='application/json')
        self.assertFalse(r.json()['success'])
        self.assertEqual(Chat.objects.count(), 0)


class CeleryBackstopTests(TestCase):
    def test_generate_ai_response_refuses_media_for_trial_user_without_spending(self):
        from aitext.tasks import generate_ai_response
        net = _network(provider='fal-ai', config_json={'api_defaults': {}})
        u = _trial()
        chat = Chat.objects.create(user=u, network=net, title='c')
        Message.objects.create(chat=chat, role='user', content='draw a cat', status='completed')
        assistant = Message.objects.create(chat=chat, role='assistant', content='', status='pending')
        generate_ai_response(assistant.id)
        assistant.refresh_from_db()
        u.refresh_from_db()
        self.assertEqual(assistant.status, Message.Status.FAILED)
        self.assertEqual(u.balance_kopecks, 100000)  # ничего не списано
        self.assertFalse(BalanceTransaction.objects.filter(user=u, type='spend').exists())

    def test_generate_ai_response_org_billed_message_bypasses_personal_gate(self):
        """skip_star_billing (org-группа) - плательщик не личный пользователь, гейт его не касается."""
        from aitext.tasks import generate_ai_response
        net = _network(provider='fal-ai', config_json={'api_defaults': {}})
        u = _trial()
        chat = Chat.objects.create(user=u, network=net, title='c')
        Message.objects.create(chat=chat, role='user', content='draw a cat', status='completed')
        assistant = Message.objects.create(
            chat=chat, role='assistant', content='', status='pending',
            settings={'skip_star_billing': True},
        )
        with mock.patch('aitext.fal_utils.get_laozhang_image_client', side_effect=RuntimeError('stop after gate')):
            try:
                generate_ai_response(assistant.id)
            except Exception:
                pass
        assistant.refresh_from_db()
        # Не должно быть немедленно провалено ИМЕННО из-за медиа-гейта (org billing пропускает его) -
        # статус может быть FAILED из-за смоделированной ошибки апстрима, но не по вине гейта.
        self.assertNotEqual(assistant.error_message, 'Генерация изображений и видео доступна только на платных тарифах.')
