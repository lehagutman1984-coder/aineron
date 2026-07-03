"""S5 — AI-Секретарь (Business Connection): бот отвечает клиентам владельца.

Режимы:
  «Черновики» (по умолчанию, безопасный старт) — AI готовит ответ по базе
  знаний владельца (Persistent Memory), шлёт владельцу на подтверждение:
  [Отправить] [Изменить] [Игнор]. Ничего не уходит без одобрения.
  «Автопилот» — авто-ответ на типовые вопросы с уведомлением владельца;
  при неуверенности AI или стоп-слове клиента — эскалация в черновики.

Всё за флагом TG_BUSINESS. Приватность: хранится только очередь черновиков
с TTL (cleanup_business_drafts), переписка клиентов не логируется.
"""
import html as html_mod
import json
import logging

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from asgiref.sync import sync_to_async
from django.conf import settings

from telegram_bot.analytics import async_log_event
from telegram_bot.utils import DIVIDER, card

logger = logging.getLogger(__name__)
router = Router()


class BizEditFSM(StatesGroup):
    editing_draft = State()


# ─── DB / LLM helpers (sync) ───

def _upsert_connection(telegram_id: int, connection_id: str, is_enabled: bool,
                       can_reply: bool):
    from telegram_bot.models import TelegramUser, BusinessConnection
    tg_user = TelegramUser.objects.filter(telegram_id=telegram_id).first()
    if tg_user is None:
        return None
    conn, _ = BusinessConnection.objects.update_or_create(
        connection_id=connection_id,
        defaults={'tg_user': tg_user, 'is_enabled': is_enabled, 'can_reply': can_reply},
    )
    return conn


def _get_connection(connection_id: str):
    from telegram_bot.models import BusinessConnection
    return (
        BusinessConnection.objects.select_related('tg_user', 'tg_user__user',
                                                  'tg_user__default_network',
                                                  'project')
        .filter(connection_id=connection_id).first()
    )


def _get_owner_connection(tg_user):
    from telegram_bot.models import BusinessConnection
    return (
        BusinessConnection.objects.select_related('project')
        .filter(tg_user=tg_user, is_enabled=True)
        .order_by('-updated_at').first()
    )


def _memory_context(user) -> str:
    """База знаний владельца: факты Persistent Memory (UserMemory)."""
    try:
        from aitext.models import UserMemory
        facts = list(
            UserMemory.objects.filter(user=user, is_active=True)
            .order_by('-is_pinned', '-created_at')[:30]
        )
        return '\n'.join(f'- {f.content}' for f in facts)
    except Exception:
        return ''


def _project_kb_context(conn, client_text: str) -> str:
    """U4 (Ш8): база знаний секретаря — RAG по файлам подключённого проекта
    (прайс, FAQ, условия — главный B2B-запрос к секретарю)."""
    if conn.project_id is None:
        return ''
    try:
        from aitext.search import hybrid_search
        chunks = hybrid_search(conn.project, [client_text[:300]], top_k=4)
        if not chunks:
            return ''
        return '\n'.join(
            f"- [{c.get('filename', '?')}] {str(c.get('text', ''))[:350]}"
            for c in chunks
        )
    except Exception as e:
        logger.warning(f'business kb context failed: {e}')
        return ''


def _generate_reply(conn, client_text: str, client_name: str) -> dict | None:
    """AI-ответ клиенту. Возвращает {'reply': str, 'confident': bool} или None."""
    from aitext.models import NeuralNetwork
    from aitext.tasks import get_laozhang_client

    network = conn.tg_user.default_network
    if network is None or not network.is_active:
        network = (
            NeuralNetwork.objects.filter(is_active=True, provider='openrouter')
            .order_by('cost_kopecks').first()
        )
    if network is None or not network.model_name:
        return None

    kb = _memory_context(conn.tg_user.user)
    project_kb = _project_kb_context(conn, client_text)  # U4: файлы проекта
    tone = conn.tone or 'вежливо, коротко и по делу'
    system = (
        'Ты — AI-секретарь владельца этого Telegram-аккаунта. Клиент написал '
        'сообщение — подготовь ответ ОТ ИМЕНИ владельца (первое лицо). '
        f'Тон: {tone}. Отвечай на языке клиента.\n'
        + (f'\nБаза знаний владельца:\n{kb}\n' if kb else '')
        + (f'\nДокументы бизнеса (прайс/FAQ/условия — приоритетный источник):\n'
           f'{project_kb}\n' if project_kb else '')
        + '\nВерни ТОЛЬКО JSON: {"reply": "текст ответа", '
        '"confident": true/false — уверен ли ты, что это типовой вопрос, '
        'на который можно ответить без владельца (часы, цены, услуги, FAQ)}. '
        'Если вопрос требует решения владельца (сделки, жалобы, нестандарт) — confident: false.'
    )
    try:
        client = get_laozhang_client()
        resp = client.chat.completions.create(
            model=network.model_name,
            messages=[
                {'role': 'system', 'content': system},
                {'role': 'user', 'content': f'{client_name}: {client_text[:2000]}'},
            ],
            max_tokens=600,
            temperature=0.4,
        )
        raw = (resp.choices[0].message.content or '').strip()
        start, end = raw.find('{'), raw.rfind('}') + 1
        if start != -1 and end > start:
            data = json.loads(raw[start:end])
            if data.get('reply'):
                return {'reply': str(data['reply']), 'confident': bool(data.get('confident'))}
        return {'reply': raw, 'confident': False} if raw else None
    except Exception as e:
        logger.warning(f'business _generate_reply failed: {e}')
        return None


def _create_draft(conn, client_chat_id: int, client_name: str,
                  incoming: str, draft: str, status: str = 'pending'):
    from telegram_bot.models import BusinessDraft
    return BusinessDraft.objects.create(
        connection=conn, client_chat_id=client_chat_id, client_name=client_name,
        incoming_text=incoming, draft_text=draft, status=status,
    )


def _get_draft(draft_id: int, tg_user):
    from telegram_bot.models import BusinessDraft
    return (
        BusinessDraft.objects.select_related('connection', 'connection__tg_user',
                                             'connection__tg_user__user')
        .filter(pk=draft_id, connection__tg_user=tg_user).first()
    )


def _charge_reply(conn, draft_id: int) -> tuple:
    """Биллинг ответа: тариф «Бизнес» — 300/мес включено, сверх — по цене
    BUSINESS_REPLY_PRICE_KOPECKS; без тарифа — каждый ответ платный.

    Возвращает (ok, paid): paid=True если было реальное списание —
    при неудачной отправке вызывающий код обязан вызвать _refund_reply.
    """
    from django.db.models import F
    from django.utils import timezone
    from telegram_bot.models import BusinessConnection
    price = getattr(settings, 'BUSINESS_REPLY_PRICE_KOPECKS', 100)
    allowance = getattr(settings, 'BUSINESS_TARIFF_ALLOWANCE', 300)
    user = conn.tg_user.user

    month = timezone.now().strftime('%Y-%m')
    if conn.replies_month != month:
        BusinessConnection.objects.filter(pk=conn.pk).update(
            replies_month=month, replies_this_month=0,
        )
        conn.replies_month, conn.replies_this_month = month, 0

    tariff_name = (getattr(user.tariff, 'display_name', '') or '').lower()
    is_business_tariff = 'бизнес' in tariff_name or 'business' in tariff_name
    free = is_business_tariff and conn.replies_this_month < allowance

    paid = False
    if not free:
        if not user.spend_kopecks(price, type='spend', reference=f'bizreply:{draft_id}'):
            return False, False
        paid = True
    # Атомарный инкремент — без гонки при параллельных клиентах
    BusinessConnection.objects.filter(pk=conn.pk).update(
        replies_this_month=F('replies_this_month') + 1,
    )
    return True, paid


def _refund_reply(conn, draft_id: int, paid: bool):
    """Возврат списания за недоставленный ответ + откат счётчика."""
    from django.db.models import F
    from django.db.models.functions import Greatest
    from telegram_bot.models import BusinessConnection
    if paid:
        price = getattr(settings, 'BUSINESS_REPLY_PRICE_KOPECKS', 100)
        conn.tg_user.user.add_kopecks(price, type='refund', reference=f'bizreply:{draft_id}')
    BusinessConnection.objects.filter(pk=conn.pk).update(
        replies_this_month=Greatest(F('replies_this_month') - 1, 0),
    )


def _mark_draft(draft_id: int, status: str, new_text: str = None):
    from telegram_bot.models import BusinessDraft
    updates = {'status': status}
    if new_text is not None:
        updates['draft_text'] = new_text
    BusinessDraft.objects.filter(pk=draft_id).update(**updates)


upsert_connection = sync_to_async(_upsert_connection, thread_sensitive=True)
get_connection = sync_to_async(_get_connection, thread_sensitive=True)
get_owner_connection = sync_to_async(_get_owner_connection, thread_sensitive=True)
generate_reply = sync_to_async(_generate_reply, thread_sensitive=True)
create_draft = sync_to_async(_create_draft, thread_sensitive=True)
get_draft = sync_to_async(_get_draft, thread_sensitive=True)
charge_reply = sync_to_async(_charge_reply, thread_sensitive=True)
refund_reply = sync_to_async(_refund_reply, thread_sensitive=True)
mark_draft = sync_to_async(_mark_draft, thread_sensitive=True)


def _draft_kb(draft_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text='Отправить', callback_data=f'bizdraft_send:{draft_id}'),
            InlineKeyboardButton(text='Изменить', callback_data=f'bizdraft_edit:{draft_id}'),
            InlineKeyboardButton(text='Игнор', callback_data=f'bizdraft_ignore:{draft_id}'),
        ],
        [InlineKeyboardButton(text='Чек-лист клиенту', callback_data=f'bizdraft_check:{draft_id}')],
    ])


async def _send_business_reply(bot, conn, chat_id: int, text: str) -> bool:
    """Ответ клиенту от имени владельца через business_connection_id."""
    try:
        await bot.send_message(
            chat_id=chat_id, text=text,
            business_connection_id=conn.connection_id,
        )
        return True
    except Exception as e:
        logger.warning(f'business reply failed ({conn.connection_id[:8]}): {e}')
        return False


# ─── Подключение Telegram Business ───

@router.business_connection()
async def on_business_connection(event, bot=None):
    """Пользователь подключил/отключил бота в Telegram Business."""
    if not getattr(settings, 'TG_BUSINESS', False):
        return
    try:
        telegram_id = event.user.id
        connection_id = event.id
        is_enabled = bool(getattr(event, 'is_enabled', True))
        rights = getattr(event, 'rights', None)
        can_reply = bool(getattr(rights, 'can_reply', False)) if rights else is_enabled
    except Exception as e:
        logger.warning(f'business_connection parse failed: {e}')
        return

    conn = await upsert_connection(telegram_id, connection_id, is_enabled, can_reply)
    b = bot or getattr(event, 'bot', None)
    if b is None:
        return
    if conn is None:
        try:
            await b.send_message(
                chat_id=telegram_id,
                text='Чтобы включить AI-секретаря, сначала привяжите аккаунт: /start',
            )
        except Exception:
            pass
        return

    if is_enabled:
        try:
            await b.send_message(
                chat_id=telegram_id,
                text=card(
                    'AI-секретарь подключён',
                    'Бот будет готовить ответы вашим клиентам.\n\n'
                    'Режим: <b>Черновики</b> — ничего не отправляется без вашего '
                    'подтверждения. Каждое сообщение клиента придёт сюда с готовым '
                    'черновиком и кнопками.\n\n'
                    'Настройки: /secretary',
                ),
                parse_mode='HTML',
            )
        except Exception:
            pass


# ─── Входящие сообщения клиентов ───

@router.business_message(F.text)
async def on_business_message(message: Message):
    if not getattr(settings, 'TG_BUSINESS', False):
        return
    connection_id = getattr(message, 'business_connection_id', None)
    if not connection_id:
        return

    conn = await get_connection(connection_id)
    if conn is None or not conn.is_enabled or not conn.secretary_on:
        return

    owner_id = conn.tg_user.telegram_id
    # Сообщение от самого владельца в его чате — не обрабатываем
    if message.from_user and message.from_user.id == owner_id:
        return

    chat_id = message.chat.id
    if not conn.scope_all and chat_id not in (conn.allowed_chat_ids or []):
        return

    client_name = (message.from_user.full_name if message.from_user else '') or 'Клиент'
    text = message.text or ''

    # Стоп-слово клиента — немедленная передача владельцу без AI
    if conn.stop_word and conn.stop_word.lower() in text.lower():
        try:
            await message.bot.send_message(
                chat_id=owner_id,
                text=card('Клиент просит человека',
                          f'<b>{html_mod.escape(client_name)}</b>: {html_mod.escape(text[:500])}\n\n'
                          'AI-секретарь передал диалог вам.'),
                parse_mode='HTML',
            )
        except Exception:
            pass
        return

    result = await generate_reply(conn, text, client_name)
    if result is None:
        return

    if conn.mode == 'autopilot' and result['confident']:
        draft = await create_draft(conn, chat_id, client_name, text,
                                   result['reply'], status='auto')
        charged, paid = await charge_reply(conn, draft.pk)
        if not charged:
            await mark_draft(draft.pk, 'pending')
            try:
                await message.bot.send_message(
                    chat_id=owner_id,
                    text='AI-секретарь: недостаточно средств для автоответа. '
                         'Черновик ждёт в /secretary, баланс — /balance.',
                )
            except Exception:
                pass
            return
        sent = await _send_business_reply(message.bot, conn, chat_id, result['reply'])
        if not sent:
            # Возврат средств + эскалация владельцу карточкой-черновиком
            await refund_reply(conn, draft.pk, paid)
            await mark_draft(draft.pk, 'pending')
            try:
                await message.bot.send_message(
                    chat_id=owner_id,
                    text=card(
                        f'Автоответ не доставлен — от {html_mod.escape(client_name)}',
                        f'{html_mod.escape(text[:600])}\n{DIVIDER}\n'
                        f'<b>Черновик ответа:</b>\n{html_mod.escape(result["reply"][:1500])}',
                    ),
                    parse_mode='HTML',
                    reply_markup=_draft_kb(draft.pk),
                )
            except Exception:
                pass
        if sent:
            await async_log_event(conn.tg_user, 'business_reply', mode='auto')
            try:
                await message.bot.send_message(
                    chat_id=owner_id,
                    text=card('Автоответ отправлен',
                              f'<b>{html_mod.escape(client_name)}</b>: {html_mod.escape(text[:300])}\n\n'
                              f'<b>Ответ AI:</b> {html_mod.escape(result["reply"][:500])}'),
                    parse_mode='HTML',
                )
            except Exception:
                pass
        return

    # Режим «Черновики» (или автопилот не уверен)
    draft = await create_draft(conn, chat_id, client_name, text, result['reply'])
    try:
        await message.bot.send_message(
            chat_id=owner_id,
            text=card(
                f'Сообщение от {html_mod.escape(client_name)}',
                f'{html_mod.escape(text[:600])}\n{DIVIDER}\n'
                f'<b>Черновик ответа:</b>\n{html_mod.escape(result["reply"][:1500])}',
            ),
            parse_mode='HTML',
            reply_markup=_draft_kb(draft.pk),
        )
    except Exception as e:
        logger.warning(f'draft delivery to owner failed: {e}')


# ─── Кнопки владельца ───

@router.callback_query(F.data.startswith('bizdraft_send:'))
async def cb_bizdraft_send(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    draft_id = int(query.data.split(':')[1])
    draft = await get_draft(draft_id, tg_user)
    if draft is None or draft.status != 'pending':
        await query.answer('Черновик не найден или уже обработан')
        return
    charged, paid = await charge_reply(draft.connection, draft.pk)
    if not charged:
        await query.answer('Недостаточно средств — пополните баланс: /balance', show_alert=True)
        return
    sent = await _send_business_reply(query.bot, draft.connection,
                                      draft.client_chat_id, draft.draft_text)
    if sent:
        await mark_draft(draft.pk, 'sent')
        await async_log_event(tg_user, 'business_reply', mode='draft')
        await query.answer('Отправлено клиенту')
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            pass
    else:
        await refund_reply(draft.connection, draft.pk, paid)
        await query.answer('Не удалось отправить (проверьте права бота в Telegram Business). '
                           'Средства возвращены.', show_alert=True)


@router.callback_query(F.data.startswith('bizdraft_ignore:'))
async def cb_bizdraft_ignore(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    draft_id = int(query.data.split(':')[1])
    draft = await get_draft(draft_id, tg_user)
    if draft:
        await mark_draft(draft.pk, 'ignored')
    await query.answer('Проигнорировано')
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass


@router.callback_query(F.data.startswith('bizdraft_edit:'))
async def cb_bizdraft_edit(query: CallbackQuery, state: FSMContext, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    draft_id = int(query.data.split(':')[1])
    await state.set_state(BizEditFSM.editing_draft)
    await state.update_data(draft_id=draft_id)
    await query.answer()
    await query.message.reply('Отправьте новый текст ответа клиенту:')


@router.message(BizEditFSM.editing_draft)
async def on_bizdraft_new_text(message: Message, state: FSMContext, tg_user=None):
    data = await state.get_data()
    await state.clear()
    if tg_user is None:
        return
    draft_id = data.get('draft_id')
    new_text = (message.text or '').strip()
    if not draft_id or not new_text:
        await message.answer('Пустой текст — черновик не изменён.')
        return
    draft = await get_draft(draft_id, tg_user)
    if draft is None or draft.status != 'pending':
        await message.answer('Черновик не найден или уже обработан.')
        return
    charged, paid = await charge_reply(draft.connection, draft.pk)
    if not charged:
        await message.answer('Недостаточно средств — пополните баланс: /balance')
        return
    sent = await _send_business_reply(message.bot, draft.connection,
                                      draft.client_chat_id, new_text)
    if sent:
        await mark_draft(draft.pk, 'sent', new_text=new_text)
        await async_log_event(tg_user, 'business_reply', mode='edited')
        await message.answer('Отправлено клиенту.')
    else:
        await refund_reply(draft.connection, draft.pk, paid)
        await message.answer('Не удалось отправить — проверьте права бота. Средства возвращены.')


@router.callback_query(F.data.startswith('bizdraft_check:'))
async def cb_bizdraft_check(query: CallbackQuery, tg_user=None):
    """Чек-лист клиенту (sendChecklist, только через business connection)."""
    if tg_user is None:
        await query.answer()
        return
    draft_id = int(query.data.split(':')[1])
    draft = await get_draft(draft_id, tg_user)
    if draft is None:
        await query.answer('Черновик не найден')
        return

    send_checklist = getattr(query.bot, 'send_checklist', None)
    if send_checklist is None:
        await query.answer('Чек-листы требуют обновления бота', show_alert=True)
        return

    @sync_to_async
    def _extract_tasks():
        from aitext.models import NeuralNetwork
        from aitext.tasks import get_laozhang_client
        network = (
            NeuralNetwork.objects.filter(is_active=True, provider='openrouter')
            .order_by('cost_kopecks').first()
        )
        if network is None:
            return []
        try:
            client = get_laozhang_client()
            resp = client.chat.completions.create(
                model=network.model_name,
                messages=[{
                    'role': 'user',
                    'content': (
                        'Извлеки из диалога договорённости и следующие шаги как '
                        'короткие пункты чек-листа. Верни ТОЛЬКО JSON-массив строк '
                        '(максимум 8 пунктов).\n\n'
                        f'Клиент: {draft.incoming_text[:800]}\n'
                        f'Ответ: {draft.draft_text[:800]}'
                    ),
                }],
                max_tokens=300,
                temperature=0.2,
            )
            raw = (resp.choices[0].message.content or '').strip()
            start, end = raw.find('['), raw.rfind(']') + 1
            if start != -1 and end > start:
                return [str(x)[:100] for x in json.loads(raw[start:end])][:8]
        except Exception as e:
            logger.warning(f'checklist extract failed: {e}')
        return []

    await query.answer('Составляю чек-лист...')
    tasks = await _extract_tasks()
    if not tasks:
        await query.message.answer('Не удалось выделить договорённости для чек-листа.')
        return
    try:
        from aiogram.types import InputChecklist, InputChecklistTask
        checklist = InputChecklist(
            title='Договорённости',
            tasks=[InputChecklistTask(id=i + 1, text=t) for i, t in enumerate(tasks)],
        )
        await send_checklist(
            business_connection_id=draft.connection.connection_id,
            chat_id=draft.client_chat_id,
            checklist=checklist,
        )
        await query.message.answer('Чек-лист отправлен клиенту.')
    except Exception as e:
        logger.warning(f'send_checklist failed: {e}')
        await query.message.answer('Не удалось отправить чек-лист (нужен Telegram Premium у владельца).')


# ─── Настройки: /secretary ───

def _secretary_kb(conn) -> InlineKeyboardMarkup:
    mode_label = 'Режим: Черновики' if conn.mode == 'drafts' else 'Режим: Автопилот'
    toggle_label = 'Выключить секретаря' if conn.secretary_on else 'Включить секретаря'
    kb_label = (f'База знаний: {conn.project.name[:25]}'
                if conn.project_id and conn.project else 'Подключить базу знаний')
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=mode_label, callback_data='biz_mode')],
        [InlineKeyboardButton(text=kb_label, callback_data='biz_kb')],
        [InlineKeyboardButton(text=toggle_label, callback_data='biz_toggle')],
    ])


@router.callback_query(F.data == 'biz_kb')
async def cb_biz_kb(query: CallbackQuery, tg_user=None):
    """U4: выбор проекта — база знаний секретаря (прайс, FAQ, условия)."""
    if tg_user is None:
        await query.answer()
        return
    conn = await get_owner_connection(tg_user)
    if conn is None:
        await query.answer('Подключение не найдено')
        return

    @sync_to_async
    def _projects():
        from aitext.models import Project
        return list(Project.objects.filter(user=tg_user.user)
                    .order_by('-created_at')[:10])

    projects = await _projects()
    if not projects:
        await query.answer('Сначала создайте проект и загрузите файлы: /projects',
                           show_alert=True)
        return
    rows = [[InlineKeyboardButton(text=p.name[:40], callback_data=f'biz_kb_set:{p.pk}')]
            for p in projects]
    rows.append([InlineKeyboardButton(text='Отключить базу знаний',
                                      callback_data='biz_kb_set:0')])
    await query.answer()
    await query.message.answer(
        'Выберите проект — его файлы (прайс, FAQ, условия) станут базой знаний '
        'секретаря при ответах клиентам:',
        reply_markup=InlineKeyboardMarkup(inline_keyboard=rows),
    )


@router.callback_query(F.data.startswith('biz_kb_set:'))
async def cb_biz_kb_set(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    project_id = int(query.data.split(':')[1])
    conn = await get_owner_connection(tg_user)
    if conn is None:
        await query.answer('Подключение не найдено')
        return

    @sync_to_async
    def _set():
        from telegram_bot.models import BusinessConnection
        from aitext.models import Project
        if project_id == 0:
            BusinessConnection.objects.filter(pk=conn.pk).update(project=None)
            return 'off'
        project = Project.objects.filter(user=tg_user.user, pk=project_id).first()
        if project is None:
            return None
        BusinessConnection.objects.filter(pk=conn.pk).update(project=project)
        return project.name

    result = await _set()
    if result is None:
        await query.answer('Проект не найден')
    elif result == 'off':
        await query.answer('База знаний отключена')
        await query.message.edit_text('База знаний секретаря отключена.')
    else:
        await query.answer('База знаний подключена')
        await query.message.edit_text(
            f'Секретарь теперь отвечает клиентам с опорой на файлы проекта '
            f'«{result}». Проверьте, что там есть прайс/FAQ.',
        )


@router.message(Command('secretary'))
async def cmd_secretary(message: Message, tg_user=None):
    if tg_user is None:
        await message.answer('Привяжите аккаунт через /start')
        return
    if not getattr(settings, 'TG_BUSINESS', False):
        await message.answer(
            'AI-секретарь скоро появится. Подробности: https://aineron.ru/business-bot/',
        )
        return
    conn = await get_owner_connection(tg_user)
    if conn is None:
        await message.answer(
            card('AI-секретарь',
                 'Бот будет отвечать вашим клиентам от вашего имени.\n\n'
                 'Подключение (нужен Telegram Business):\n'
                 'Настройки → Telegram Business → Чат-боты → '
                 f'@{getattr(settings, "TELEGRAM_BOT_USERNAME", "aineron_bot")}\n\n'
                 'После подключения все сообщения клиентов будут приходить сюда '
                 'с готовыми черновиками ответов.'),
            parse_mode='HTML',
        )
        return

    from django.utils import timezone
    month = timezone.now().strftime('%Y-%m')
    replies = conn.replies_this_month if conn.replies_month == month else 0
    allowance = getattr(settings, 'BUSINESS_TARIFF_ALLOWANCE', 300)
    mode_h = 'Черновики (безопасный)' if conn.mode == 'drafts' else 'Автопилот'
    status = 'включён' if conn.secretary_on else 'выключен'
    await message.answer(
        card('AI-секретарь',
             f'Статус: <b>{status}</b>\n'
             f'Режим: <b>{mode_h}</b>\n'
             f'Ответов в этом месяце: {replies} (в тарифе «Бизнес» {allowance} включено)\n'
             f'Стоп-слово клиента: «{conn.stop_word}»'),
        parse_mode='HTML',
        reply_markup=_secretary_kb(conn),
    )


@router.callback_query(F.data == 'biz_mode')
async def cb_biz_mode(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    conn = await get_owner_connection(tg_user)
    if conn is None:
        await query.answer('Подключение не найдено')
        return

    @sync_to_async
    def _toggle_mode():
        conn.mode = 'autopilot' if conn.mode == 'drafts' else 'drafts'
        conn.save(update_fields=['mode'])
        return conn.mode

    new_mode = await _toggle_mode()
    if new_mode == 'autopilot':
        await query.answer('Автопилот: типовые вопросы — сразу клиенту, остальное — вам')
    else:
        await query.answer('Черновики: всё через ваше подтверждение')
    try:
        await query.message.edit_reply_markup(reply_markup=_secretary_kb(conn))
    except Exception:
        pass


@router.callback_query(F.data == 'biz_toggle')
async def cb_biz_toggle(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        await query.answer()
        return
    conn = await get_owner_connection(tg_user)
    if conn is None:
        await query.answer('Подключение не найдено')
        return

    @sync_to_async
    def _toggle():
        conn.secretary_on = not conn.secretary_on
        conn.save(update_fields=['secretary_on'])
        return conn.secretary_on

    on = await _toggle()
    await query.answer('Секретарь включён' if on else 'Секретарь выключен')
    try:
        await query.message.edit_reply_markup(reply_markup=_secretary_kb(conn))
    except Exception:
        pass
