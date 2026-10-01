"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 6/17):
регрессионный тест — неизвестная ЯВНО указанная модель в /v1/images/generations
больше не тихо подменяется на случайную активную, а отдаёт model_not_found.
Пустой model (клиент не указал) по-прежнему берёт разумный дефолт.

Запуск: python manage.py test api.tests_images_model_resolve
"""
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from rest_framework import status

from aitext.models import Category, NeuralNetwork
from users.models import PaymentHistory

User = get_user_model()


def _paying_user(email='imguser@t.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.save(update_fields=['email_verified'])
    u.set_kopecks(100000)
    PaymentHistory.objects.create(
        user=u, payment_type='pages', payment_method='test',
        invoice_id=f'test-{u.id}', amount='1.00', amount_kopecks=100, status='success',
    )
    return u


class ImageModelResolveTests(APITestCase):
    def setUp(self):
        cat, _ = Category.objects.get_or_create(name='TestImg', defaults={'slug': 'testimg'})
        self.real_model = NeuralNetwork.objects.create(
            name='Real Image Model', slug='real-image-model', model_name='real-image-model',
            category=cat, cost_per_message=10, cost_kopecks=1000, provider='fal-ai', is_active=True,
        )
        self.user = _paying_user()
        self.client.force_authenticate(user=self.user)

    def test_unknown_explicit_model_rejected_not_substituted(self):
        resp = self.client.post('/api/v1/images/generations', {
            'model': 'typo-nonexistent-model', 'prompt': 'a cat',
        }, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['error']['code'], 'model_not_found')
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100000)  # ничего не списано

    def test_no_model_specified_falls_back_to_active_default(self):
        fake_resp = SimpleNamespace(data=[SimpleNamespace(url='https://example.com/a.png')])
        with mock.patch('api.views.images.get_laozhang_image_client') as get_client:
            get_client.return_value.images.generate.return_value = fake_resp
            resp = self.client.post('/api/v1/images/generations', {'prompt': 'a cat'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        call_kwargs = get_client.return_value.images.generate.call_args.kwargs
        self.assertEqual(call_kwargs.get('model'), 'real-image-model')
