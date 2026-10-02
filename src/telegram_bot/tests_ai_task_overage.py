"""
2026-10-02 (аудит безопасности, №25): execute_ai_task() биллился ТОЛЬКО по
плоской network.cost_kopecks, независимо от реального размера prompt/ответа.
task.network - произвольная (в т.ч. самая дорогая) модель, task.prompt без
ограничения длины - до AITASK_DAILY_CAP раз в день. Теперь реальный перерасход
против флоат-цены доплачивается через compute_overage(), как в обычном чате.
"""
from datetime import time as dtime
from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from aitext.models import Category, NeuralNetwork
from telegram_bot.models import AITask, TelegramUser
from users.models import BalanceTransaction

User = get_user_model()
LOCMEM = {'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'}}

OVERAGE_ON = dict(
    CACHES=LOCMEM, TOKEN_OVERAGE_ENABLED=True, TOKEN_OVERAGE_DRY_RUN=False,
    TOKEN_OVERAGE_MODELS=['claude-opus-5'], TOKEN_OVERAGE_USD_RUB=80,
    TOKEN_OVERAGE_MARKUP=1.6, TOKEN_OVERAGE_MIN_FRACTION=0.25,
    TOKEN_OVERAGE_MIN_KOPECKS=100, TOKEN_OVERAGE_CAP_MULTIPLE=2.0,
    TOKEN_OVERAGE_ABS_CAP_KOPECKS=100000, AITASK_DAILY_CAP=30,
)


def _network(model_name='claude-opus-5', cost_kopecks=300):
    cat, _ = Category.objects.get_or_create(name='T25', defaults={'slug': 't25'})
    return NeuralNetwork.objects.create(
        name=model_name, slug=model_name, model_name=model_name, category=cat,
        cost_per_message=3, cost_kopecks=cost_kopecks, provider='openrouter', is_active=True,
    )


def _task_user(balance=1_000_000, email='aitask@t.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.set_kopecks(balance)
    TelegramUser.objects.create(user=u, telegram_id=hash(email) % 10**9)
    return u


def _completion(content='answer', prompt_tokens=10, completion_tokens=10):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=prompt_tokens, completion_tokens=completion_tokens),
    )


@override_settings(**OVERAGE_ON)
class AITaskOverageTests(TestCase):
    def setUp(self):
        self.network = _network()
        self.user = _task_user()
        self.task = AITask.objects.create(
            user=self.user, prompt='Небольшой промт', network=self.network,
            schedule_type=AITask.Schedule.DAILY, run_time=dtime(9, 0),
            deliver_chat_id=555, use_web_search=False,  # не дёргать реальный Tavily в тестах
        )

    @mock.patch('telegram_bot.notify.notify_user_rich', return_value=True)
    @mock.patch('aitext.tasks.get_laozhang_client')
    def test_huge_prompt_charges_real_overage_not_just_flat(self, get_client, notify):
        """Огромный promt (много реальных токенов) к дорогой аудированной
        модели должен доплатить разницу поверх плоской цены - не остаться
        бесплатным/заниженным, как до фикса."""
        get_client.return_value.chat.completions.create.return_value = _completion(
            prompt_tokens=50_000, completion_tokens=1500,
        )
        from telegram_bot.tasks import execute_ai_task
        execute_ai_task.apply(args=[self.task.id, '2026-10-02T09:00:00'])

        self.user.refresh_from_db()
        spent = 1_000_000 - self.user.balance_kopecks
        self.assertGreater(spent, self.network.cost_kopecks)  # не только плоская цена
        self.assertTrue(
            BalanceTransaction.objects.filter(
                user=self.user, type='spend', reference__endswith=':overage'
            ).exists()
        )

    @mock.patch('telegram_bot.notify.notify_user_rich', return_value=True)
    @mock.patch('aitext.tasks.get_laozhang_client')
    def test_small_response_no_overage_charged(self, get_client, notify):
        """Обычный маленький запрос - реальная себестоимость с запасом
        покрывается плоской ценой, доплаты быть не должно (как и раньше)."""
        get_client.return_value.chat.completions.create.return_value = _completion(
            prompt_tokens=50, completion_tokens=50,
        )
        from telegram_bot.tasks import execute_ai_task
        execute_ai_task.apply(args=[self.task.id, '2026-10-02T09:00:01'])

        self.user.refresh_from_db()
        spent = 1_000_000 - self.user.balance_kopecks
        self.assertEqual(spent, self.network.cost_kopecks)
        self.assertFalse(
            BalanceTransaction.objects.filter(
                user=self.user, type='spend', reference__endswith=':overage'
            ).exists()
        )

    @mock.patch('telegram_bot.notify.notify_user_rich', return_value=False)
    @mock.patch('aitext.tasks.get_laozhang_client')
    def test_delivery_failure_refunds_overage_too(self, get_client, notify):
        """Если доставка в Telegram не удалась, возврат должен включать
        и доплату, а не только плоскую часть - иначе деньги теряются молча."""
        get_client.return_value.chat.completions.create.return_value = _completion(
            prompt_tokens=50_000, completion_tokens=1500,
        )
        from telegram_bot.tasks import execute_ai_task
        execute_ai_task.apply(args=[self.task.id, '2026-10-02T09:00:02'])

        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 1_000_000)  # всё вернулось

    @override_settings(TOKEN_OVERAGE_ENABLED=False)
    @mock.patch('telegram_bot.notify.notify_user_rich', return_value=True)
    @mock.patch('aitext.tasks.get_laozhang_client')
    def test_overage_disabled_falls_back_to_flat_only(self, get_client, notify):
        """TOKEN_OVERAGE_ENABLED=0 - старое поведение (плоская цена) без
        доплаты, как и для остальной системы (общий рубильник уважается)."""
        get_client.return_value.chat.completions.create.return_value = _completion(
            prompt_tokens=50_000, completion_tokens=1500,
        )
        from telegram_bot.tasks import execute_ai_task
        execute_ai_task.apply(args=[self.task.id, '2026-10-02T09:00:03'])

        self.user.refresh_from_db()
        spent = 1_000_000 - self.user.balance_kopecks
        self.assertEqual(spent, self.network.cost_kopecks)
