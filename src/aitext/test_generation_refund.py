"""
2026-08-06: живым E2E-тестом на проде обнаружено, что реальные пользователи
теряли деньги при провале генерации, классифицированном как "deprecated
free model" (aitext/tasks.py::generate_ai_response, ветка `if status_code
== 404 or 'deprecated' in error_str.lower() or 'free model' in
error_str.lower()`). Эта ветка делает `return` раньше общего блока возврата
средств внизу функции — pre-charge оставался списанным даже на платных
моделях (нашлись 2 реальных пострадавших: chat 3010 claude-opus-5 22 ₽,
chat 3189 claude-fable-5 15 ₽ — оба вручную возвращены после находки).

Django TestCase (SQLite): python manage.py test aitext.test_generation_refund
"""
from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.test import TestCase

from aitext.models import Category, Chat, Message, NeuralNetwork
from aitext.tasks import generate_ai_response
from users.models import BalanceTransaction

User = get_user_model()


class _FakeAPIError(Exception):
    """Без status_code — как реальная ошибка провайдера в этом сценарии
    (совпадение попадает только по тексту 'free model'/'deprecated')."""


def _make_network(**kwargs):
    cat, _ = Category.objects.get_or_create(name='Test', defaults={'slug': 'test'})
    defaults = dict(
        name='Test Model', slug='test-model-refund', model_name='claude-fable-5',
        category=cat, cost_per_message=15, cost_kopecks=1500, provider='openrouter',
        is_free=False,
    )
    defaults.update(kwargs)
    return NeuralNetwork.objects.create(**defaults)


class DeprecatedModelBranchRefundTests(TestCase):
    """§ Ветка free_model_deprecated обязана вернуть pre-charge, как и
    общий путь окончательного провала — независимо от того, действительно
    ли модель бесплатная (текстовое совпадение 'free model' может сработать
    и на платной модели, как в реальном инциденте)."""

    def setUp(self):
        self.user = User.objects.create_user(username='refundtest', email='refundtest@t.ru', password='x')
        self.user.balance_kopecks = 100_000
        self.user.save(update_fields=['balance_kopecks'])
        self.network = _make_network()
        self.chat = Chat.objects.create(user=self.user, network=self.network, title='t', settings={})
        Message.objects.create(chat=self.chat, role='user', content='привет', status=Message.Status.COMPLETED)

        # Имитируем pre-charge, как это делает api/views/chats.py перед
        # постановкой задачи в очередь.
        reference = 'chat:pending'
        self.user.spend_kopecks(1500, type='spend', reference=reference)
        self.user.refresh_from_db()
        self.balance_after_charge = self.user.balance_kopecks
        self.assistant_message = Message.objects.create(
            chat=self.chat, role='assistant', status=Message.Status.PENDING, content='',
            settings={'billing_reference': reference, 'billing_kopecks': 1500},
        )

    def _run_with_provider_error(self, error_text):
        fake_client = MagicMock()
        fake_client.chat.completions.create.side_effect = _FakeAPIError(error_text)
        with patch('aitext.tasks.get_client_for_network', return_value=fake_client):
            generate_ai_response.apply(args=[self.assistant_message.id])

    def test_platform_model_misclassified_as_free_still_gets_refunded(self):
        """Реальный инцидент: claude-fable-5 (платная) — текст ошибки
        провайдера случайно содержал 'free model'."""
        self._run_with_provider_error("Error: no channel available for this free model tier")

        self.assistant_message.refresh_from_db()
        self.user.refresh_from_db()

        self.assertEqual(self.assistant_message.status, Message.Status.FAILED)
        self.assertNotIn('free model', self.assistant_message.error_message.lower())
        self.assertEqual(self.user.balance_kopecks, self.balance_after_charge + 1500)
        self.assertTrue(
            BalanceTransaction.objects.filter(
                user=self.user, type=BalanceTransaction.Type.REFUND, reference='chat:pending',
            ).exists()
        )

    def test_deprecated_keyword_also_refunds(self):
        self._run_with_provider_error("Error: this model has been deprecated by the provider")

        self.assistant_message.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.assistant_message.status, Message.Status.FAILED)
        self.assertEqual(self.user.balance_kopecks, self.balance_after_charge + 1500)

    def test_double_run_does_not_double_refund(self):
        """Ретрай (или повторная обработка того же message_id) не должен
        начислить деньги дважды — idempotent по unique(type, reference)."""
        self._run_with_provider_error("free model unavailable")
        self._run_with_provider_error("free model unavailable")

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, self.balance_after_charge + 1500)
        self.assertEqual(
            BalanceTransaction.objects.filter(
                user=self.user, type=BalanceTransaction.Type.REFUND, reference='chat:pending',
            ).count(),
            1,
        )
