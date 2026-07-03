import logging
import time
from celery import shared_task
from asgiref.sync import async_to_sync

logger = logging.getLogger(__name__)

_DIGEST_PROMPT = (
    "Сделай краткий ежедневный дайджест для пользователя AI-платформы. "
    "Включи: 1) Один интересный факт или новость об AI, "
    "2) Практический совет по работе с языковыми моделями, "
    "3) Краткую мотивирующую мысль. "
    "Формат: лаконично, 3 абзаца с эмодзи. Отвечай на русском."
)


@shared_task(bind=True, max_retries=2, ignore_result=True,
             name='telegram_bot.tasks.send_daily_digests')
def send_daily_digests(self):
    """
    Runs every minute; sends digest to users whose digest_hour:digest_minute
    matches the current Moscow time.
    """
    import pytz
    from datetime import datetime

    moscow = pytz.timezone('Europe/Moscow')
    now_moscow = datetime.now(moscow)
    current_hour = now_moscow.hour
    current_minute = now_moscow.minute

    try:
        from telegram_bot.models import TelegramUser
        users = list(TelegramUser.objects.filter(
            digest_enabled=True,
            digest_hour=current_hour,
            digest_minute=current_minute,
        ).select_related('user', 'default_network'))
    except Exception as e:
        logger.warning(f"send_daily_digests: query failed: {e}")
        return

    if not users:
        return

    logger.info(
        f"send_daily_digests: sending to {len(users)} users "
        f"at {current_hour}:{current_minute:02d} MSK"
    )
    for tg_user in users:
        try:
            _send_digest_to_user(tg_user)
        except Exception as e:
            logger.warning(f"send_daily_digests: failed for {tg_user.telegram_id}: {e}")


def _send_digest_to_user(tg_user):
    from aitext.tasks import get_laozhang_client
    from aitext.models import NeuralNetwork

    user = tg_user.user
    if not user:
        return

    network = tg_user.default_network
    if not network:
        network = (
            NeuralNetwork.objects
            .filter(is_active=True, handle_photo=False, handle_video=False)
            .order_by('cost_kopecks')
            .first()
        )
    if not network or not network.model_name:
        return

    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model=network.model_name,
            messages=[
                {"role": "system", "content": "Ты — полезный AI-ассистент платформы aineron.ru."},
                {"role": "user", "content": _DIGEST_PROMPT},
            ],
            max_tokens=600,
            temperature=0.7,
        )
        content = resp.choices[0].message.content or ""
    except Exception as e:
        logger.warning(f"send_daily_digests: AI call failed: {e}")
        return

    if not content.strip():
        return

    text = (
        f"*Ваш ежедневный AI-дайджест*\n\n{content}"
        f"\n\n_aineron.ru_ — отключить: /digest off"
    )
    async_to_sync(_bot_send)(tg_user.telegram_id, text)


async def _bot_send(telegram_id: int, text: str):
    from aiogram import Bot
    from django.conf import settings as dj_settings
    bot = Bot(token=dj_settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode='Markdown')
    finally:
        await bot.session.close()


@shared_task(name='telegram_bot.tasks.notify_low_balance')
def notify_low_balance():
    """Notify Telegram users with low balance. Run daily via Celery Beat."""
    try:
        from telegram_bot.models import TelegramUser
        from telegram_bot.notify import notify_user
        from django.core.cache import cache

        threshold = 5
        tg_users = list(
            TelegramUser.objects.select_related('user').filter(
                user__isnull=False, user__pages_count__lte=threshold,
            )
        )
        notified = 0
        for tu in tg_users:
            cache_key = f'tg_low_bal_{tu.telegram_id}'
            if cache.get(cache_key):
                continue
            notify_user(
                tu.telegram_id,
                f'Баланс заканчивается: <b>{tu.user.pages_count} зв.</b>\n'
                f'Пополни чтобы продолжить: /balance',
            )
            cache.set(cache_key, True, timeout=86400)
            notified += 1
        logger.info(f'notify_low_balance: {notified} notified')
    except Exception as e:
        logger.error(f'notify_low_balance error: {e}')


@shared_task(bind=True, max_retries=2, ignore_result=True,
             name='telegram_bot.tasks.send_reminders')
def send_reminders(self):
    """
    Runs every minute; dispatches due reminders that haven't been sent yet.
    Registered via DatabaseScheduler PeriodicTask (see management/commands/setup_periodic_tasks.py).
    """
    from django.utils import timezone as tz
    from telegram_bot.models import Reminder

    now = tz.now()
    due = list(Reminder.objects.filter(is_sent=False, remind_at__lte=now).select_related('tg_user'))
    if not due:
        return

    logger.info(f'send_reminders: {len(due)} due')
    ids_ok = []
    for reminder in due:
        try:
            text = f'Напоминание:\n\n{reminder.text}'
            async_to_sync(_bot_send)(reminder.tg_user.telegram_id, text)
            ids_ok.append(reminder.pk)
        except Exception as e:
            logger.warning(f'send_reminders: failed {reminder.pk}: {e}')

    if ids_ok:
        Reminder.objects.filter(pk__in=ids_ok).update(is_sent=True)


@shared_task(bind=True, max_retries=1, ignore_result=True,
             name='telegram_bot.tasks.summarize_poll')
def summarize_poll(self, poll_session_id: int):
    """Generate AI summary for a closed PollSession and deliver to creator."""
    from telegram_bot.models import PollSession
    from aitext.models import NeuralNetwork
    from aitext.tasks import get_laozhang_client

    try:
        session = PollSession.objects.select_related('tg_user', 'tg_user__default_network').get(pk=poll_session_id)
    except PollSession.DoesNotExist:
        return

    if not session.options or not session.vote_counts:
        return

    lines = []
    for opt, cnt in zip(session.options, session.vote_counts):
        lines.append(f'  - {opt}: {cnt} голос(ов)')

    prompt = (
        f'Вопрос опроса: «{session.question}»\n'
        f'Результаты:\n' + '\n'.join(lines) + '\n\n'
        'Сделай краткий аналитический вывод: кто победил, что это значит, '
        'как можно использовать эти данные. Отвечай на русском, 3-5 предложений.'
    )

    network = session.tg_user.default_network
    if not network:
        network = NeuralNetwork.objects.filter(is_active=True, provider='openrouter').order_by('cost_kopecks').first()
    if not network or not network.model_name:
        return

    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model=network.model_name,
            messages=[{'role': 'user', 'content': prompt}],
            max_tokens=400,
            temperature=0.5,
        )
        summary = (resp.choices[0].message.content or '').strip()
    except Exception as e:
        logger.warning(f'summarize_poll: AI call failed: {e}')
        return

    PollSession.objects.filter(pk=poll_session_id).update(ai_summary=summary)

    import html as html_mod
    text = (f'Опрос завершён!\n\n<b>Вопрос:</b> {html_mod.escape(session.question)}\n\n'
            f'<b>AI-анализ:</b>\n{html_mod.escape(summary)}')
    async_to_sync(_bot_send_html)(session.tg_user.telegram_id, text)


async def _bot_send_html(telegram_id: int, text: str):
    from aiogram import Bot
    from django.conf import settings as dj_settings
    bot = Bot(token=dj_settings.TELEGRAM_BOT_TOKEN)
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode='HTML')
    finally:
        await bot.session.close()


# ═══════════════════════════════════════════════════════════════════════════
# S2 — AI-Задачи: проактивный агент по расписанию (TELEGRAM_SUPREMACY_PLAN)
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=0, ignore_result=True,
             name='telegram_bot.tasks.run_due_ai_tasks')
def run_due_ai_tasks(self):
    """Каждую минуту: находит просроченные AI-задачи и ставит их на исполнение.

    Клейм атомарный (conditional UPDATE next_run_at) — двойной запуск при
    перекрытии beat-тиков невозможен; списание дополнительно идемпотентно
    по reference aitask:{id}:{run_iso}.
    """
    from django.utils import timezone as tz
    from telegram_bot.models import AITask

    now = tz.now()
    due = list(
        AITask.objects.filter(is_active=True, next_run_at__isnull=False, next_run_at__lte=now)
        .order_by('next_run_at')[:500]
    )
    if not due:
        return

    logger.info(f'run_due_ai_tasks: {len(due)} due')
    for task in due:
        run_iso = task.next_run_at.isoformat()
        next_run = task.compute_next_run(after=now)
        update_fields = {'next_run_at': next_run}
        if next_run is None:
            update_fields['is_active'] = False
            update_fields['paused_reason'] = 'completed'
        # Атомарный клейм: обновится только если next_run_at не изменился
        claimed = AITask.objects.filter(pk=task.pk, next_run_at=task.next_run_at).update(**update_fields)
        if claimed:
            execute_ai_task.delay(task.pk, run_iso)


@shared_task(bind=True, max_retries=1, ignore_result=True,
             name='telegram_bot.tasks.execute_ai_task')
def execute_ai_task(self, task_id: int, run_iso: str):
    """Исполнение одной AI-задачи: web-поиск → LLM → rich-доставка в Telegram.

    Списание по цене модели, идемпотентно по reference aitask:{id}:{run_iso}.
    При нехватке средств — авто-пауза с кнопкой «Пополнить».
    """
    from django.conf import settings as dj_settings
    from django.core.cache import cache
    from django.utils import timezone as tz
    from telegram_bot.models import AITask, TelegramEvent
    from telegram_bot.notify import notify_user_rich, notify_user
    from aitext.models import NeuralNetwork
    from aitext.tasks import get_laozhang_client
    from core.money import format_rub

    try:
        task = AITask.objects.select_related('user', 'network', 'project').get(pk=task_id)
    except AITask.DoesNotExist:
        return

    # U3: research-задача — автономный мониторинг темы (отдельный пайплайн)
    if getattr(task, 'kind', 'llm') == 'research':
        _execute_research_task(task, run_iso)
        return

    user = task.user
    tg = getattr(user, 'telegram', None)
    chat_id = task.deliver_chat_id or (tg.telegram_id if tg else None)
    if chat_id is None:
        logger.warning(f'execute_ai_task {task_id}: no delivery chat')
        return

    # Дневной cap исполнений на пользователя (юнит-экономика, риск §5.3)
    cap = getattr(dj_settings, 'AITASK_DAILY_CAP', 30)
    cap_key = f'aitask_cap:{user.pk}:{tz.now().date().isoformat()}'
    ran_today = cache.get(cap_key, 0)
    if ran_today >= cap:
        logger.warning(f'execute_ai_task {task_id}: daily cap {cap} reached for user {user.pk}')
        return

    network = task.network
    if network is None or not network.is_active:
        network = (
            NeuralNetwork.objects
            .filter(is_active=True, provider='openrouter')
            .order_by('cost_kopecks')
            .first()
        )
    if network is None or not network.model_name:
        logger.warning(f'execute_ai_task {task_id}: no network available')
        return

    cost = network.cost_kopecks
    reference = f'aitask:{task_id}:{run_iso}'

    # Авто-пауза при балансе ниже стоимости запуска
    if not user.has_enough_kopecks(cost):
        AITask.objects.filter(pk=task_id).update(is_active=False, paused_reason='balance')
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Пополнить', url=f'{dj_settings.SITE_URL}/account/billing/')],
            ])
        except Exception:
            kb = None
        notify_user_rich(
            chat_id,
            f'**Задача на паузе: недостаточно средств**\n\n'
            f'«{task.title or task.prompt[:60]}» — нужно {format_rub(cost)} за запуск.\n'
            f'Пополните баланс и включите задачу снова: /tasks',
            reply_markup=kb,
        )
        return

    if not user.spend_kopecks(cost, type='spend', reference=reference):
        AITask.objects.filter(pk=task_id).update(is_active=False, paused_reason='balance')
        return

    # Web-поиск (Tavily) при флаге
    search_context = ''
    if task.use_web_search:
        try:
            from aitext.web_search import web_search
            search_context = web_search(task.prompt, max_results=5) or ''
        except Exception as e:
            logger.warning(f'execute_ai_task {task_id}: web_search failed: {e}')

    import pytz
    from datetime import datetime
    now_msk = datetime.now(pytz.timezone('Europe/Moscow'))
    system = (
        'Ты — проактивный AI-агент платформы aineron.ru, выполняющий задачу '
        'пользователя по расписанию. Отвечай на русском, структурировано '
        '(markdown: заголовки, списки, таблицы где уместно), лаконично и по делу. '
        f'Сейчас {now_msk.strftime("%d.%m.%Y %H:%M")} МСК.'
    )
    user_content = task.prompt
    if search_context:
        user_content += f'\n\nАктуальные результаты веб-поиска:\n{search_context}'

    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model=network.model_name,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': user_content},
            ],
            max_tokens=1500,
            temperature=0.6,
        )
        content = (resp.choices[0].message.content or '').strip()
        if not content:
            raise ValueError('empty LLM response')
    except Exception as e:
        logger.error(f'execute_ai_task {task_id}: LLM failed: {e}')
        user.add_kopecks(cost, type='refund', reference=reference)
        notify_user(chat_id, 'Не удалось выполнить AI-задачу — средства возвращены. Попробую в следующий раз.')
        return

    title = task.title or 'AI-задача'
    md = f'**{title}**\n\n{content}\n\n_{network.name} · {format_rub(cost)} · управление: /tasks_'
    delivered = notify_user_rich(chat_id, md)
    if not delivered:
        # Пользователь заблокировал бота / чат недоступен: возврат средств
        # и пауза задачи, чтобы не списывать деньги в никуда каждый запуск
        user.add_kopecks(cost, type='refund', reference=reference)
        AITask.objects.filter(pk=task_id).update(is_active=False, paused_reason='delivery')
        logger.warning(f'execute_ai_task {task_id}: delivery failed, refunded and paused')
        return

    cache.set(cap_key, ran_today + 1, timeout=86400)

    from django.db.models import F
    updates = {'last_run_at': tz.now(), 'runs_count': F('runs_count') + 1}
    AITask.objects.filter(pk=task_id).update(**updates)
    task.refresh_from_db(fields=['runs_count'])
    if task.max_runs and task.runs_count >= task.max_runs:
        AITask.objects.filter(pk=task_id).update(is_active=False, paused_reason='max_runs')

    try:
        TelegramEvent.objects.create(
            telegram_user=tg, event_type='task_run', network=network,
            cost_kopecks=cost, meta={'task_id': task_id, 'run': run_iso},
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# S5 — AI-секретарь: утренняя сводка и TTL-очистка черновиков
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(name='telegram_bot.tasks.business_daily_summary', bind=True,
             max_retries=0, ignore_result=True)
def business_daily_summary(self):
    """Утренняя сводка владельцу: сколько сообщений обработано за сутки."""
    from datetime import timedelta
    from django.conf import settings as dj
    from django.utils import timezone as tz
    from django.db.models import Count, Q
    from telegram_bot.models import BusinessConnection
    from telegram_bot.notify import notify_user

    if not getattr(dj, 'TG_BUSINESS', False):
        return

    day_ago = tz.now() - timedelta(hours=24)
    connections = (
        BusinessConnection.objects.filter(is_enabled=True, secretary_on=True)
        .select_related('tg_user')
        .annotate(
            total=Count('drafts', filter=Q(drafts__created_at__gte=day_ago)),
            auto=Count('drafts', filter=Q(drafts__created_at__gte=day_ago,
                                          drafts__status='auto')),
            sent=Count('drafts', filter=Q(drafts__created_at__gte=day_ago,
                                          drafts__status='sent')),
            pending=Count('drafts', filter=Q(drafts__created_at__gte=day_ago,
                                             drafts__status='pending')),
        )
    )
    for conn in connections:
        if not conn.total:
            continue
        try:
            notify_user(
                conn.tg_user.telegram_id,
                f'<b>AI-секретарь · сводка за сутки</b>\n'
                f'Сообщений клиентов: <b>{conn.total}</b>\n'
                f'Отвечено автоматически: {conn.auto}\n'
                f'Отправлено вами: {conn.sent}\n'
                f'Ждут решения: {conn.pending}\n\n'
                f'Управление: /secretary',
            )
        except Exception as e:
            logger.warning(f'business_daily_summary failed for {conn.pk}: {e}')


@shared_task(name='telegram_bot.tasks.cleanup_business_drafts', bind=True,
             max_retries=0, ignore_result=True)
def cleanup_business_drafts(self):
    """Приватность: черновики с текстами клиентов живут максимум 7 дней."""
    from datetime import timedelta
    from django.utils import timezone as tz
    from telegram_bot.models import BusinessDraft

    cutoff = tz.now() - timedelta(days=7)
    deleted, _ = BusinessDraft.objects.filter(created_at__lt=cutoff).delete()
    if deleted:
        logger.info(f'cleanup_business_drafts: {deleted} deleted')


@shared_task(name='telegram_bot.tasks.cleanup_group_message_logs', bind=True,
             max_retries=0, ignore_result=True)
def cleanup_group_message_logs(self):
    """S7: лог групповых сообщений для /summary живёт максимум 48 часов."""
    from datetime import timedelta
    from django.utils import timezone as tz
    from telegram_bot.models import GroupMessageLog

    cutoff = tz.now() - timedelta(hours=48)
    deleted, _ = GroupMessageLog.objects.filter(created_at__lt=cutoff).delete()
    if deleted:
        logger.info(f'cleanup_group_message_logs: {deleted} deleted')


# ═══════════════════════════════════════════════════════════════════════════
# Retention-гигиена (Roadmap H2 2026): onboarding-loop и weekly-отчёт админам
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=0, ignore_result=True,
             name='telegram_bot.tasks.offer_first_ai_task')
def offer_first_ai_task(self):
    """Onboarding-loop: пользователям, привязавшим бота 1–3 дня назад и не
    создавшим ни одной AI-задачи, предлагаем «Утренний бриф» одной кнопкой.
    Конверсия в ежедневную привычку — главный retention-рычаг S2."""
    from datetime import timedelta
    from django.core.cache import cache
    from django.utils import timezone as tz
    from telegram_bot.models import TelegramUser, AITask
    from telegram_bot.notify import notify_user

    now = tz.now()
    candidates = list(
        TelegramUser.objects.select_related('user')
        .filter(linked_at__gte=now - timedelta(days=3),
                linked_at__lte=now - timedelta(days=1))[:200]
    )
    offered = 0
    for tu in candidates:
        cache_key = f'tg_task_offer:{tu.telegram_id}'
        if cache.get(cache_key):
            continue
        if AITask.objects.filter(user=tu.user).exists():
            continue
        try:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text='Включить утренний бриф',
                                     callback_data='task_preset:brief'),
            ]])
            from telegram_bot.notify import notify_user_rich
            notify_user_rich(
                tu.telegram_id,
                '**Совет дня**\n\nЯ умею работать по расписанию, пока вы спите: '
                'каждое утро — свежие новости AI, курс доллара и идея дня. '
                'Одна кнопка — и бриф будет ждать вас в 8:00.',
                reply_markup=kb,
            )
            cache.set(cache_key, True, timeout=30 * 86400)
            offered += 1
        except Exception as e:
            logger.debug(f'offer_first_ai_task failed for {tu.telegram_id}: {e}')
    if offered:
        logger.info(f'offer_first_ai_task: {offered} offered')


@shared_task(bind=True, max_retries=0, ignore_result=True,
             name='telegram_bot.tasks.admin_weekly_report')
def admin_weekly_report(self):
    """Понедельничный отчёт админам: DAU/новые пользователи/выручка/супер-фичи."""
    from datetime import timedelta
    from django.conf import settings as dj
    from django.db.models import Count, Sum
    from django.utils import timezone as tz
    from telegram_bot.models import TelegramUser, TelegramEvent, AITask
    from telegram_bot.notify import notify_user
    from core.money import format_rub

    admin_ids = getattr(dj, 'TELEGRAM_ADMIN_IDS', [])
    if not admin_ids:
        return

    week_ago = tz.now() - timedelta(days=7)
    new_users = TelegramUser.objects.filter(linked_at__gte=week_ago).count()
    wau = (TelegramEvent.objects.filter(created_at__gte=week_ago)
           .values('telegram_user').distinct().count())
    by_type = dict(
        TelegramEvent.objects.filter(created_at__gte=week_ago)
        .values_list('event_type').annotate(n=Count('id'))
        .values_list('event_type', 'n')
    )
    revenue = (TelegramEvent.objects.filter(
        created_at__gte=week_ago, event_type__in=['payment', 'subscription'])
        .aggregate(s=Sum('cost_kopecks'))['s'] or 0)
    active_tasks = AITask.objects.filter(is_active=True).count()

    text = (
        '<b>Aineron · недельный отчёт бота</b>\n'
        f'Новых пользователей: <b>{new_users}</b>\n'
        f'WAU: <b>{wau}</b>\n'
        f'Платежи + подписки: <b>{format_rub(revenue)}</b>\n\n'
        f'Сообщений: {by_type.get("message", 0)}\n'
        f'Изображений: {by_type.get("image", 0)} · Видео: {by_type.get("video", 0)}\n'
        f'AI-задач исполнено: {by_type.get("task_run", 0)} (активных: {active_tasks})\n'
        f'Research: {by_type.get("research", 0)} · Agent: {by_type.get("agent", 0)}\n'
        f'Секретарь: {by_type.get("business_reply", 0)} ответов\n'
        f'Stars-подписок оформлено/продлено: {by_type.get("subscription", 0)}'
    )
    for admin_id in admin_ids:
        try:
            notify_user(admin_id, text)
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════════════════════
# S9 — Agent Mode: многошаговый агент с инструментами
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=0, ignore_result=True, soft_time_limit=240,
             name='telegram_bot.tasks.run_agent')
def run_agent(self, agent_run_id: int):
    """Цикл агента: LLM планирует шаг → инструмент (search/calc) → наблюдение →
    ... → finish с отчётом. Списание фиксированное (AGENT_PRICE_KOPECKS),
    идемпотентно agent:{run_id}; при ошибке или недоставке — возврат."""
    from django.conf import settings as dj
    from django.utils import timezone as tz
    from telegram_bot.models import AgentRun, TelegramEvent
    from telegram_bot.notify import notify_user_rich, notify_user
    from telegram_bot.agent import AGENT_SYSTEM, MAX_STEPS, safe_calc, parse_action, step_human
    from aitext.models import NeuralNetwork
    from aitext.tasks import get_laozhang_client
    from core.money import format_rub

    try:
        run = AgentRun.objects.select_related('user').get(pk=agent_run_id)
    except AgentRun.DoesNotExist:
        return

    user = run.user
    tg = getattr(user, 'telegram', None)
    if tg is None:
        return
    chat_id = tg.telegram_id
    price = getattr(dj, 'AGENT_PRICE_KOPECKS', 500)
    reference = f'agent:{agent_run_id}'

    def _fail(msg: str, refund: bool = True):
        if refund:
            user.add_kopecks(price, type='refund', reference=reference)
        AgentRun.objects.filter(pk=agent_run_id).update(
            status='error', error=msg[:500], finished_at=tz.now(),
        )
        notify_user(chat_id, f'{msg} Средства возвращены.' if refund else msg)

    if not user.spend_kopecks(price, type='spend', reference=reference):
        AgentRun.objects.filter(pk=agent_run_id).update(status='error', error='no_balance')
        notify_user(chat_id, 'Недостаточно средств для Agent Mode. Пополните баланс: /balance')
        return

    network = (
        tg.default_network
        if tg.default_network and tg.default_network.is_active
        else NeuralNetwork.objects.filter(is_active=True, provider='openrouter')
        .order_by('cost_kopecks').first()
    )
    if network is None or not network.model_name:
        _fail('Нет доступных моделей.')
        return

    run.status = 'running'
    run.save(update_fields=['status'])
    run.append_step('start', 'Планирую выполнение задачи...')

    client = get_laozhang_client()
    messages = [
        {'role': 'system', 'content': AGENT_SYSTEM},
        {'role': 'user', 'content': run.goal[:2000]},
    ]
    report = ''

    try:
        for step_no in range(1, MAX_STEPS + 1):
            resp = client.chat.completions.create(
                model=network.model_name,
                messages=messages,
                max_tokens=1800,
                temperature=0.3,
            )
            raw = (resp.choices[0].message.content or '').strip()
            action = parse_action(raw)
            if action is None:
                # LLM ответил не по протоколу — принимаем текст как финал
                report = raw
                break

            messages.append({'role': 'assistant', 'content': raw})

            if action['action'] == 'finish':
                report = action['input']
                break

            run.append_step(action['action'], step_human(action))

            if action['action'] == 'search':
                try:
                    from aitext.web_search import web_search
                    observation = web_search(action['input'], max_results=5) or 'Ничего не найдено.'
                except Exception as e:
                    observation = f'Поиск недоступен: {e}'
            else:  # calc
                observation = safe_calc(action['input'])

            messages.append({
                'role': 'user',
                'content': f'Наблюдение (шаг {step_no}): {observation[:4000]}',
            })
        else:
            # Лимит шагов исчерпан — просим финализировать
            messages.append({'role': 'user',
                             'content': 'Лимит шагов исчерпан. Дай финальный отчёт сейчас.'})
            resp = client.chat.completions.create(
                model=network.model_name, messages=messages,
                max_tokens=1800, temperature=0.3,
            )
            raw = (resp.choices[0].message.content or '').strip()
            action = parse_action(raw)
            report = action['input'] if action and action['action'] == 'finish' else raw
    except Exception as e:
        logger.error(f'run_agent {agent_run_id} failed: {e}', exc_info=True)
        _fail('Agent Mode: ошибка выполнения.')
        return

    if not report.strip():
        _fail('Agent Mode: пустой результат.')
        return

    run.append_step('done', 'Задача выполнена')
    AgentRun.objects.filter(pk=agent_run_id).update(
        status='done', result_md=report, finished_at=tz.now(),
    )

    delivered = notify_user_rich(
        chat_id,
        f'{report}\n\n_Agent Mode · {format_rub(price)} · {network.name}_',
    )
    if not delivered:
        user.add_kopecks(price, type='refund', reference=reference)
        return

    try:
        TelegramEvent.objects.create(
            telegram_user=tg, event_type='agent', network=network,
            cost_kopecks=price, meta={'run_id': agent_run_id, 'steps': len(run.steps)},
        )
    except Exception:
        pass


# ═══════════════════════════════════════════════════════════════════════════
# S8 — Managed Bots: ответ гостю персонального бота
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(bind=True, max_retries=1, ignore_result=True,
             name='telegram_bot.tasks.managed_bot_reply')
def managed_bot_reply(self, bot_id: int, chat_id: int, text: str, message_id: int):
    """Гость написал персональному боту → LLM-ответ от имени агента.

    Биллинг — с баланса владельца, идемпотентно по
    managedbot:{bot_id}:{chat_id}:{message_id}.
    """
    from aiogram import Bot
    from telegram_bot.models import ManagedBot
    from aitext.models import NeuralNetwork
    from aitext.tasks import get_laozhang_client

    managed = (
        ManagedBot.objects.select_related('owner', 'owner__user', 'network', 'project')
        .filter(pk=bot_id, is_active=True).first()
    )
    if managed is None:
        return

    async def _send(reply_text: str):
        b = Bot(token=managed.token)
        try:
            await b.send_message(chat_id=chat_id, text=reply_text[:4000])
        except Exception as e:
            logger.warning(f'managed_bot_reply send failed ({bot_id}): {e}')
        finally:
            await b.session.close()

    # /start — приветствие без LLM и без списания
    if text.startswith('/start'):
        async_to_sync(_send)(managed.greeting or 'Привет! Задайте вопрос.')
        return

    owner = managed.owner.user
    network = managed.network
    if network is None or not network.is_active:
        network = (
            NeuralNetwork.objects.filter(is_active=True, provider='openrouter')
            .order_by('cost_kopecks').first()
        )
    if network is None or not network.model_name:
        return

    reference = f'managedbot:{bot_id}:{chat_id}:{message_id}'
    if not owner.spend_kopecks(network.cost_kopecks, type='spend', reference=reference):
        async_to_sync(_send)('Бот временно недоступен. Загляните позже.')
        try:
            from telegram_bot.notify import notify_user
            notify_user(
                managed.owner.telegram_id,
                f'Персональный бот @{managed.bot_username} остановлен: '
                f'недостаточно средств. Пополните баланс: /balance',
            )
        except Exception:
            pass
        return

    # База знаний: RAG по проекту владельца (реюз механизма deep research)
    kb_context = ''
    if managed.project_id:
        try:
            from aitext.tasks import _kb_search_chunks
            chunks = _kb_search_chunks(managed.project, text, top_k=4)
            if chunks:
                kb_context = '\n'.join(f'- {c["text"][:300]}' for c in chunks)
        except Exception as e:
            logger.warning(f'managed_bot_reply kb failed: {e}')

    system = (
        f'Ты — AI-агент «{managed.name}». '
        + (managed.system_prompt or 'Отвечай полезно и вежливо.')
        + (f'\n\nБаза знаний:\n{kb_context}' if kb_context else '')
        + '\nОтвечай на языке собеседника, лаконично.'
    )
    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model=network.model_name,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': text[:2000]},
            ],
            max_tokens=800,
            temperature=0.6,
        )
        reply = (resp.choices[0].message.content or '').strip()
        if not reply:
            raise ValueError('empty reply')
    except Exception as e:
        logger.error(f'managed_bot_reply LLM failed ({bot_id}): {e}')
        owner.add_kopecks(network.cost_kopecks, type='refund', reference=reference)
        async_to_sync(_send)('Не удалось ответить, попробуйте ещё раз.')
        return

    async_to_sync(_send)(reply)

    from django.db.models import F
    ManagedBot.objects.filter(pk=bot_id).update(messages_count=F('messages_count') + 1)


# ═══════════════════════════════════════════════════════════════════════════
# S4 — Подарки за активность (за флагом TG_GIFTS, бюджет в env)
# ═══════════════════════════════════════════════════════════════════════════

@shared_task(name='telegram_bot.tasks.send_activity_gifts', bind=True, max_retries=0,
             ignore_result=True)
def send_activity_gifts(self):
    """Еженедельно: подарок за 30-дневный streak активности или 3+ приведённых
    друзей за месяц. Умеренно — лимит бюджета TG_GIFTS_MONTHLY_BUDGET_STARS."""
    import asyncio
    from datetime import timedelta
    from django.conf import settings as dj
    from django.core.cache import cache
    from django.utils import timezone as tz
    from django.db.models import Count
    from telegram_bot.models import TelegramUser, TelegramEvent
    from users.models import CustomUser

    if not getattr(dj, 'TG_GIFTS', False):
        return

    budget = getattr(dj, 'TG_GIFTS_MONTHLY_BUDGET_STARS', 500)
    month_key = f'tg_gifts_spent:{tz.now().strftime("%Y-%m")}'
    spent = cache.get(month_key, 0)
    if spent >= budget:
        return

    month_ago = tz.now() - timedelta(days=30)

    # Кандидаты: 30 разных дней активности за месяц ИЛИ 3+ рефералов за месяц
    from django.db.models.functions import TruncDate
    streak_ids = set(
        TelegramEvent.objects.filter(created_at__gte=month_ago)
        .annotate(day=TruncDate('created_at'))
        .values('telegram_user')
        .annotate(days=Count('day', distinct=True))
        .filter(days__gte=30)
        .values_list('telegram_user', flat=True)
    )
    referrer_user_ids = set(
        CustomUser.objects.filter(date_joined__gte=month_ago, referrer__isnull=False)
        .values('referrer')
        .annotate(n=Count('id'))
        .filter(n__gte=3)
        .values_list('referrer', flat=True)
    )
    candidates = list(
        TelegramUser.objects.filter(
            models_q_or(streak_ids, referrer_user_ids)
        ).select_related('user')[:20]
    ) if (streak_ids or referrer_user_ids) else []

    if not candidates:
        return

    async def _gift_all(users):
        nonlocal spent
        from aiogram import Bot
        bot = Bot(token=dj.TELEGRAM_BOT_TOKEN)
        try:
            send_gift = getattr(bot, 'send_gift', None)
            get_gifts = getattr(bot, 'get_available_gifts', None)
            if send_gift is None or get_gifts is None:
                return
            gifts = await get_gifts()
            gift_list = sorted(getattr(gifts, 'gifts', []), key=lambda g: g.star_count)
            if not gift_list:
                return
            cheapest = gift_list[0]
            for tu in users:
                if spent + cheapest.star_count > budget:
                    break
                # не дарить дважды в месяц
                user_key = f'tg_gift_sent:{tu.telegram_id}:{tz.now().strftime("%Y-%m")}'
                if cache.get(user_key):
                    continue
                try:
                    await send_gift(
                        user_id=tu.telegram_id, gift_id=cheapest.id,
                        text='Спасибо за активность в aineron!',
                    )
                    spent += cheapest.star_count
                    cache.set(user_key, True, timeout=32 * 86400)
                    cache.set(month_key, spent, timeout=32 * 86400)
                except Exception as e:
                    logger.warning(f'send_activity_gifts: gift to {tu.telegram_id} failed: {e}')
        finally:
            await bot.session.close()

    try:
        asyncio.run(_gift_all(candidates))
        logger.info(f'send_activity_gifts: budget spent {spent}/{budget}')
    except Exception as e:
        logger.error(f'send_activity_gifts error: {e}')


def models_q_or(streak_tg_user_ids, referrer_user_ids):
    """Q-объект: TelegramUser по pk из streak-списка или по user_id из рефереров."""
    from django.db.models import Q
    q = Q(pk__in=list(streak_tg_user_ids))
    if referrer_user_ids:
        q = q | Q(user_id__in=list(referrer_user_ids))
    return q


def _execute_research_task(task, run_iso: str):
    """U3 — исполнение research-задачи: движок deep_research по расписанию.

    Цена — RESEARCH_PRICE_KOPECKS (как ручной /research), идемпотентно
    aitask:{id}:{run_iso}. Отчёт: доставка в Telegram + автосохранение в базу
    знаний проекта (компаундинг — следующий запуск видит прошлые отчёты).
    """
    from django.conf import settings as dj
    from django.utils import timezone as tz
    from django.db.models import F
    from telegram_bot.models import AITask, TelegramEvent
    from telegram_bot.notify import notify_user_rich, notify_user
    from aitext.models import Chat, Message as AiMsg, NeuralNetwork, DeepResearch
    from core.money import format_rub

    user = task.user
    tg = getattr(user, 'telegram', None)
    chat_id = task.deliver_chat_id or (tg.telegram_id if tg else None)
    if chat_id is None:
        return

    price = getattr(dj, 'RESEARCH_PRICE_KOPECKS', 1000)
    reference = f'aitask:{task.pk}:{run_iso}'

    if not user.has_enough_kopecks(price):
        AITask.objects.filter(pk=task.pk).update(is_active=False, paused_reason='balance')
        notify_user(chat_id,
                    f'Research-задача «{task.title or ""}» на паузе: нужно '
                    f'{format_rub(price)} за запуск. Пополните баланс: /balance')
        return
    if not user.spend_kopecks(price, type='spend', reference=reference):
        AITask.objects.filter(pk=task.pk).update(is_active=False, paused_reason='balance')
        return

    network = task.network if (task.network and task.network.is_active) else (
        NeuralNetwork.objects.filter(is_active=True, provider='openrouter')
        .order_by('cost_kopecks').first()
    )
    if network is None:
        user.add_kopecks(price, type='refund', reference=reference)
        return

    # Research-чат в проекте задачи (компаундинг: KB проекта участвует в поиске)
    chat = Chat.objects.create(
        user=user, network=network, project=task.project,
        title=f'Monitor: {task.title or task.prompt[:50]}',
    )
    AiMsg.objects.create(chat=chat, role='user', content=task.prompt,
                         plain_text=task.prompt, status='completed')
    assistant_msg = AiMsg.objects.create(chat=chat, role='assistant',
                                         content='', plain_text='', status='pending')
    research = DeepResearch.objects.create(chat=chat, message=assistant_msg,
                                           question=task.prompt)

    # Синхронный запуск движка (мы уже в Celery-воркере)
    from aitext.tasks import deep_research_task
    try:
        deep_research_task.apply(args=[research.pk])
    except Exception as e:
        logger.error(f'_execute_research_task {task.pk}: engine failed: {e}')

    research.refresh_from_db()
    if research.status != 'done':
        user.add_kopecks(price, type='refund', reference=reference)
        notify_user(chat_id, f'Research-задача «{task.title or ""}»: ошибка '
                             f'исследования — средства возвращены.')
        return

    report_md = (assistant_msg.__class__.objects.filter(pk=assistant_msg.pk)
                 .values_list('plain_text', flat=True).first() or '')

    # Компаундинг: сохранить в KB проекта (если задан)
    saved_note = ''
    if task.project_id and getattr(dj, 'RESEARCH_TO_KB', True):
        try:
            from aitext.tasks import save_research_to_kb
            pf = save_research_to_kb(research.pk)
            if pf is not None:
                saved_note = f'\n\n_Отчёт сохранён в базу знаний проекта: {pf.filename}_'
        except Exception as e:
            logger.warning(f'_execute_research_task save to KB failed: {e}')

    title = task.title or 'Мониторинг'
    delivered = notify_user_rich(
        chat_id,
        f'**{title}**\n\n{report_md[:3500]}{saved_note}\n\n'
        f'_Research · {format_rub(price)} · управление: /tasks_',
    )
    if not delivered:
        user.add_kopecks(price, type='refund', reference=reference)
        AITask.objects.filter(pk=task.pk).update(is_active=False, paused_reason='delivery')
        return

    AITask.objects.filter(pk=task.pk).update(
        last_run_at=tz.now(), runs_count=F('runs_count') + 1,
    )
    try:
        TelegramEvent.objects.create(
            telegram_user=tg, event_type='research', network=network,
            cost_kopecks=price, meta={'task_id': task.pk, 'run': run_iso},
        )
    except Exception:
        pass


@shared_task(name='telegram_bot.tasks.broadcast_message', bind=True, max_retries=0)
def broadcast_message(self, text: str, admin_tg_id: int):
    """Send broadcast to all linked Telegram users. ~20 msg/s."""
    try:
        from telegram_bot.models import TelegramUser
        from telegram_bot.notify import notify_user

        tg_ids = list(
            TelegramUser.objects.filter(user__isnull=False).values_list('telegram_id', flat=True)
        )
        sent = 0
        failed = 0
        for tg_id in tg_ids:
            try:
                notify_user(tg_id, text)
                sent += 1
                time.sleep(0.05)
            except Exception:
                failed += 1
        try:
            notify_user(admin_tg_id, f'Рассылка завершена: {sent} отправлено, {failed} ошибок.')
        except Exception:
            pass
        logger.info(f'broadcast_message: {sent} sent, {failed} failed')
    except Exception as e:
        logger.error(f'broadcast_message error: {e}')
