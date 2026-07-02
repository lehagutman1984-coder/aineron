"""S2 — AI-Задачи: /task (создание, NL-парсер, пресеты) и /tasks (управление).

«Первый AI-агент в русском Telegram, который работает, пока ты спишь».
Главный путь создания — естественный язык: «каждое утро в 8 присылай новости
AI и курс доллара» → LLM-парсер → карточка подтверждения → AITask.
"""
import html
import json
import logging
import re

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async

from telegram_bot.analytics import async_log_event
from telegram_bot.utils import DIVIDER, card

logger = logging.getLogger(__name__)
router = Router()

# Фразы-триггеры интента «создать задачу» прямо в чате
INTENT_RE = re.compile(
    r'(кажд(ый|ое|ую)\s+(день|утро|вечер|недел)|ежедневно|еженедельно|'
    r'по расписанию|напоминай\s|следи за\s|присылай\s+(каждый|каждое|по))',
    re.IGNORECASE,
)

PRESETS = {
    'brief': {
        'title': 'Утренний бриф',
        'prompt': ('Сделай утренний бриф: 3 главные новости AI за последние сутки '
                   '(коротко, с сутью), текущий курс доллара и евро к рублю, '
                   'и одна практическая идея дня по использованию нейросетей.'),
        'schedule_type': 'daily', 'time': '08:00', 'use_web_search': True,
    },
    'currency': {
        'title': 'Курс валют и крипты',
        'prompt': ('Пришли текущие курсы: USD/RUB, EUR/RUB, BTC/USD, ETH/USD. '
                   'Одной короткой таблицей + одно предложение о динамике за сутки.'),
        'schedule_type': 'daily', 'time': '09:00', 'use_web_search': True,
    },
    'news': {
        'title': 'Мониторинг новостей',
        'prompt': None,  # тема запрашивается через FSM
        'schedule_type': 'daily', 'time': '10:00', 'use_web_search': True,
    },
    'post': {
        'title': 'Еженедельный пост',
        'prompt': None,  # тема запрашивается через FSM
        'schedule_type': 'weekly', 'time': '10:00', 'weekday': 0, 'use_web_search': True,
    },
}


class TaskFSM(StatesGroup):
    confirming = State()
    preset_topic = State()


# ─── DB-хелперы ───

def _active_count(user):
    from telegram_bot.models import AITask
    return AITask.objects.filter(user=user, is_active=True).count()


def _task_limit(user):
    from telegram_bot.models import ai_task_limit
    return ai_task_limit(user)


def _create_task(user, parsed: dict):
    """Создаёт AITask из распарсенного словаря, возвращает объект."""
    import pytz
    from datetime import datetime, time as dtime
    from django.utils import timezone
    from telegram_bot.models import AITask

    run_time = None
    if parsed.get('time'):
        try:
            h, m = str(parsed['time']).split(':')
            run_time = dtime(int(h), int(m))
        except Exception:
            run_time = dtime(9, 0)

    task = AITask(
        user=user,
        title=(parsed.get('title') or '')[:120],
        prompt=parsed.get('prompt') or '',
        schedule_type=parsed.get('schedule_type') or 'daily',
        run_time=run_time,
        weekday=parsed.get('weekday'),
        cron=parsed.get('cron') or '',
        use_web_search=bool(parsed.get('use_web_search', True)),
        created_from='bot',
    )
    if task.schedule_type == 'once':
        moscow = pytz.timezone('Europe/Moscow')
        date_str = parsed.get('date')
        now_msk = timezone.now().astimezone(moscow)
        try:
            day = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else now_msk.date()
        except Exception:
            day = now_msk.date()
        candidate = moscow.localize(datetime.combine(day, run_time or dtime(9, 0)))
        if candidate <= now_msk:
            from datetime import timedelta
            candidate += timedelta(days=1)
        task.next_run_at = candidate.astimezone(pytz.UTC)
    else:
        task.next_run_at = task.compute_next_run()
    task.save()
    return task


def _list_tasks(user):
    from telegram_bot.models import AITask
    return list(AITask.objects.filter(user=user).order_by('-is_active', '-created_at')[:20])


def _get_task(user, task_id):
    from telegram_bot.models import AITask
    return AITask.objects.filter(user=user, pk=task_id).first()


def _set_task_state(user, task_id, active: bool):
    from telegram_bot.models import AITask
    task = AITask.objects.filter(user=user, pk=task_id).first()
    if not task:
        return None
    task.is_active = active
    task.paused_reason = '' if active else 'user'
    if active and task.schedule_type != 'once':
        task.next_run_at = task.compute_next_run()
    task.save(update_fields=['is_active', 'paused_reason', 'next_run_at'])
    return task


def _delete_task(user, task_id):
    from telegram_bot.models import AITask
    return AITask.objects.filter(user=user, pk=task_id).delete()[0]


def _parse_task_nl(text: str) -> dict | None:
    """LLM-парсер естественного языка → структура задачи (DeepSeek, дёшево)."""
    from aitext.models import NeuralNetwork
    from aitext.tasks import get_laozhang_client
    from django.utils import timezone

    network = (
        NeuralNetwork.objects.filter(is_active=True, provider='openrouter',
                                     model_name__icontains='deepseek')
        .order_by('cost_kopecks').first()
    ) or (
        NeuralNetwork.objects.filter(is_active=True, provider='openrouter')
        .order_by('cost_kopecks').first()
    )
    if network is None or not network.model_name:
        return None

    today = timezone.now().strftime('%Y-%m-%d')
    system = (
        'Ты — парсер задач по расписанию. Извлеки из фразы пользователя параметры '
        'и верни ТОЛЬКО JSON без пояснений, схема:\n'
        '{"title": "короткое название до 60 символов", '
        '"prompt": "что должен сделать AI при каждом запуске (императив, без упоминания расписания)", '
        '"schedule_type": "once|daily|weekly", '
        '"time": "HH:MM (МСК, по умолчанию 09:00)", '
        '"date": "YYYY-MM-DD или null (только для once)", '
        '"weekday": 0-6 или null (0=понедельник, только для weekly), '
        '"use_web_search": true если нужны актуальные данные из интернета (новости, курсы, погода)}\n'
        f'Сегодня {today}. Если расписание не указано — daily 09:00.'
    )
    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model=network.model_name,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': text[:1000]},
            ],
            max_tokens=400,
            temperature=0.1,
        )
        raw = (resp.choices[0].message.content or '').strip()
        start, end = raw.find('{'), raw.rfind('}') + 1
        if start == -1 or end <= start:
            return None
        parsed = json.loads(raw[start:end])
        if not parsed.get('prompt'):
            return None
        if parsed.get('schedule_type') not in ('once', 'daily', 'weekly'):
            parsed['schedule_type'] = 'daily'
        return parsed
    except Exception as e:
        logger.warning(f'_parse_task_nl failed: {e}')
        return None


active_count = sync_to_async(_active_count, thread_sensitive=True)
task_limit = sync_to_async(_task_limit, thread_sensitive=True)
create_task = sync_to_async(_create_task, thread_sensitive=True)
list_tasks = sync_to_async(_list_tasks, thread_sensitive=True)
get_task = sync_to_async(_get_task, thread_sensitive=True)
set_task_state = sync_to_async(_set_task_state, thread_sensitive=True)
delete_task = sync_to_async(_delete_task, thread_sensitive=True)
parse_task_nl = sync_to_async(_parse_task_nl, thread_sensitive=True)


def _presets_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Утренний бриф (8:00)', callback_data='task_preset:brief')],
        [InlineKeyboardButton(text='Курс валют и крипты (9:00)', callback_data='task_preset:currency')],
        [InlineKeyboardButton(text='Мониторинг новостей по теме', callback_data='task_preset:news')],
        [InlineKeyboardButton(text='Еженедельный пост по теме', callback_data='task_preset:post')],
        [InlineKeyboardButton(text='Мои задачи', callback_data='task_list')],
    ])


def _confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='Создать', callback_data='task_confirm'),
            InlineKeyboardButton(text='Отмена', callback_data='task_cancel'),
        ],
    ])


def _confirm_card(parsed: dict) -> str:
    sched = {'once': 'один раз', 'daily': 'ежедневно', 'weekly': 'еженедельно'}.get(
        parsed.get('schedule_type'), parsed.get('schedule_type'))
    time_s = parsed.get('time') or '09:00'
    days = ['пн', 'вт', 'ср', 'чт', 'пт', 'сб', 'вс']
    extra = ''
    if parsed.get('schedule_type') == 'weekly' and parsed.get('weekday') is not None:
        try:
            extra = f' ({days[int(parsed["weekday"])]})'
        except Exception:
            pass
    if parsed.get('schedule_type') == 'once' and parsed.get('date'):
        extra = f' {parsed["date"]}'
    web = 'да' if parsed.get('use_web_search', True) else 'нет'
    return card(
        'Новая AI-задача',
        f'<b>{html.escape(parsed.get("title") or "Без названия")}</b>\n\n'
        f'{html.escape(parsed.get("prompt") or "")}\n\n'
        f'Расписание: {sched}{extra} в {time_s} МСК\n'
        f'Веб-поиск: {web}',
        'Каждый запуск оплачивается по цене сообщения модели.',
    )


async def _start_confirmation(message: Message, state: FSMContext, tg_user, parsed: dict):
    count = await active_count(tg_user.user)
    limit = await task_limit(tg_user.user)
    if count >= limit:
        await message.answer(
            card('Лимит задач',
                 f'Активных задач: {count} из {limit} по вашему тарифу.\n'
                 f'Поставьте одну на паузу (/tasks) или улучшите тариф: /balance'),
            parse_mode='HTML',
        )
        return
    await state.set_state(TaskFSM.confirming)
    await state.update_data(parsed=parsed)
    await message.answer(_confirm_card(parsed), parse_mode='HTML', reply_markup=_confirm_kb())


@router.message(Command('task'))
async def cmd_task(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await message.answer('Привяжите аккаунт через /start')
        return
    text = (message.text or '').removeprefix('/task').strip()
    if not text:
        await message.answer(
            card('AI-задачи по расписанию',
                 'Опишите задачу своими словами:\n\n'
                 '<code>/task каждое утро в 8 присылай новости AI и курс доллара</code>\n\n'
                 'Или выберите готовый сценарий:'),
            parse_mode='HTML',
            reply_markup=_presets_kb(),
        )
        return

    thinking = await message.answer('Разбираю задачу...')
    parsed = await parse_task_nl(text)
    try:
        await thinking.delete()
    except Exception:
        pass
    if parsed is None:
        await message.answer(
            'Не удалось разобрать задачу. Сформулируйте иначе, например:\n'
            '<code>/task каждый день в 9 утра присылай 3 новости про нейросети</code>',
            parse_mode='HTML',
        )
        return
    await _start_confirmation(message, state, tg_user, parsed)


@router.message(Command('tasks'))
async def cmd_tasks(message: Message, tg_user=None):
    if tg_user is None:
        await message.answer('Привяжите аккаунт через /start')
        return
    await _send_task_list(message, tg_user)


async def _send_task_list(message: Message, tg_user):
    tasks = await list_tasks(tg_user.user)
    if not tasks:
        await message.answer(
            card('AI-задачи',
                 'У вас пока нет задач.\n\n'
                 'Создайте первую: <code>/task каждое утро присылай новости AI</code>'),
            parse_mode='HTML',
            reply_markup=_presets_kb(),
        )
        return

    count = await active_count(tg_user.user)
    limit = await task_limit(tg_user.user)
    await message.answer(
        card('AI-задачи', f'Активных: {count} из {limit} по тарифу.'),
        parse_mode='HTML',
    )
    for t in tasks:
        status = 'активна' if t.is_active else {
            'balance': 'пауза — нет средств',
            'max_runs': 'завершена (лимит запусков)',
            'completed': 'выполнена',
        }.get(t.paused_reason, 'на паузе')
        body = (
            f'{html.escape(t.prompt[:200])}\n\n'
            f'Расписание: {t.schedule_human()}\n'
            f'Статус: {status} · запусков: {t.runs_count}'
        )
        buttons = [[
            InlineKeyboardButton(
                text='Пауза' if t.is_active else 'Включить',
                callback_data=f'task_toggle:{t.pk}',
            ),
            InlineKeyboardButton(text='Сейчас', callback_data=f'task_now:{t.pk}'),
            InlineKeyboardButton(text='Удалить', callback_data=f'task_del:{t.pk}'),
        ]]
        await message.answer(
            card(html.escape(t.title or 'AI-задача'), body),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
        )


@router.callback_query(F.data == 'task_list')
async def cb_task_list(query: CallbackQuery, tg_user=None):
    await query.answer()
    if tg_user is None:
        return
    await _send_task_list(query.message, tg_user)


@router.callback_query(F.data == 'task_confirm', TaskFSM.confirming)
async def cb_task_confirm(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    data = await state.get_data()
    parsed = data.get('parsed')
    await state.clear()
    if not parsed:
        await query.answer('Данные задачи потеряны, начните заново: /task')
        return
    task = await create_task(tg_user.user, parsed)
    await query.message.edit_text(
        card('Задача создана',
             f'<b>{html.escape(task.title or "AI-задача")}</b>\n'
             f'Расписание: {task.schedule_human()}\n\n'
             f'Первый запуск пришлю автоматически. Управление: /tasks'),
        parse_mode='HTML',
    )
    await query.answer('Задача создана')
    await async_log_event(tg_user, 'task_run', task_id=task.pk, action='created')


@router.callback_query(F.data == 'task_cancel', TaskFSM.confirming)
async def cb_task_cancel(query: CallbackQuery, state: FSMContext):
    await state.clear()
    await query.message.edit_text('Создание задачи отменено.')
    await query.answer()


@router.callback_query(F.data.startswith('task_preset:'))
async def cb_task_preset(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    key = query.data.split(':', 1)[1]
    preset = PRESETS.get(key)
    if not preset:
        await query.answer('Неизвестный сценарий')
        return
    await query.answer()
    if preset['prompt'] is None:
        await state.set_state(TaskFSM.preset_topic)
        await state.update_data(preset_key=key)
        ask = ('О какой теме следить? Например: «квантовые компьютеры», «рынок недвижимости Москвы»'
               if key == 'news' else
               'На какую тему готовить еженедельный пост? Например: «новости AI для маркетологов»')
        await query.message.answer(ask)
        return
    await _start_confirmation(query.message, state, tg_user, dict(preset))


@router.message(TaskFSM.preset_topic)
async def on_preset_topic(message: Message, state: FSMContext, tg_user=None):
    if tg_user is None:
        await state.clear()
        return
    topic = (message.text or '').strip()
    if not topic:
        await message.answer('Пустая тема — отмена. /task чтобы начать заново.')
        await state.clear()
        return
    data = await state.get_data()
    key = data.get('preset_key', 'news')
    preset = dict(PRESETS.get(key, PRESETS['news']))
    if key == 'news':
        preset['title'] = f'Новости: {topic[:90]}'
        preset['prompt'] = (
            f'Найди и перескажи главные новости по теме «{topic}» за последние сутки. '
            f'Если новостей нет — так и скажи одной строкой. Формат: краткий список с сутью.'
        )
    else:
        preset['title'] = f'Пост: {topic[:90]}'
        preset['prompt'] = (
            f'Напиши готовый пост для Telegram-канала на тему «{topic}»: цепляющее начало, '
            f'полезная суть, короткий вывод. Учитывай события последней недели.'
        )
    await _start_confirmation(message, state, tg_user, preset)


@router.callback_query(F.data.startswith('task_toggle:'))
async def cb_task_toggle(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    task_id = int(query.data.split(':')[1])
    existing = await get_task(tg_user.user, task_id)
    if existing is None:
        await query.answer('Задача не найдена')
        return
    if not existing.is_active:
        count = await active_count(tg_user.user)
        limit = await task_limit(tg_user.user)
        if count >= limit:
            await query.answer(f'Лимит активных задач: {limit}. Поставьте другую на паузу.', show_alert=True)
            return
    task = await set_task_state(tg_user.user, task_id, not existing.is_active)
    await query.answer('Задача включена' if task.is_active else 'Задача на паузе')
    status = 'активна' if task.is_active else 'на паузе'
    try:
        await query.message.edit_text(
            card(html.escape(task.title or 'AI-задача'),
                 f'{html.escape(task.prompt[:200])}\n\n'
                 f'Расписание: {task.schedule_human()}\n'
                 f'Статус: {status} · запусков: {task.runs_count}'),
            parse_mode='HTML',
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text='Пауза' if task.is_active else 'Включить',
                    callback_data=f'task_toggle:{task.pk}',
                ),
                InlineKeyboardButton(text='Сейчас', callback_data=f'task_now:{task.pk}'),
                InlineKeyboardButton(text='Удалить', callback_data=f'task_del:{task.pk}'),
            ]]),
        )
    except Exception:
        pass


@router.callback_query(F.data.startswith('task_now:'))
async def cb_task_now(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    task_id = int(query.data.split(':')[1])
    task = await get_task(tg_user.user, task_id)
    if task is None:
        await query.answer('Задача не найдена')
        return
    from django.utils import timezone
    from telegram_bot.tasks import execute_ai_task
    run_iso = f'manual:{timezone.now().isoformat()}'
    execute_ai_task.delay(task.pk, run_iso)
    await query.answer('Запускаю — результат пришлю сообщением')


@router.callback_query(F.data.startswith('task_del:'))
async def cb_task_del(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    task_id = int(query.data.split(':')[1])
    deleted = await delete_task(tg_user.user, task_id)
    if deleted:
        await query.answer('Задача удалена')
        try:
            await query.message.delete()
        except Exception:
            pass
    else:
        await query.answer('Задача не найдена')


# ─── Детект интента в чате (вызывается из chat.py) ───

@router.callback_query(F.data == 'task_intent')
async def cb_task_intent(query: CallbackQuery, state: FSMContext, tg_user=None):
    """Пользователь согласился превратить фразу из чата в задачу."""
    if tg_user is None:
        await query.answer()
        return
    from django.core.cache import cache
    get_cached = sync_to_async(cache.get, thread_sensitive=True)
    text = await get_cached(f'tg_task_intent:{tg_user.telegram_id}')
    if not text:
        await query.answer('Фраза устарела — используйте /task', show_alert=True)
        return
    await query.answer()
    thinking = await query.message.answer('Разбираю задачу...')
    parsed = await parse_task_nl(text)
    try:
        await thinking.delete()
    except Exception:
        pass
    if parsed is None:
        await query.message.answer('Не удалось разобрать. Попробуйте /task <описание>.')
        return
    await _start_confirmation(query.message, state, tg_user, parsed)


def looks_like_task_intent(text: str) -> bool:
    """Быстрая эвристика для chat.py: фраза похожа на запрос задачи по расписанию."""
    return bool(text and INTENT_RE.search(text))
