import asyncio
import logging
from asgiref.sync import sync_to_async
from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery

from django.conf import settings as dj_settings

from telegram_bot import capabilities
from telegram_bot.keyboards import after_answer_kb, main_reply_kb
from telegram_bot.notify import (
    stream_draft_or_edit, set_status_reaction, send_rich_or_markdown,
)
from telegram_bot.rich import extract_first_code
from telegram_bot.utils import telegram_format, split_message, DIVIDER
from telegram_bot.analytics import async_log_event
from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()


class EditMsgFSM(StatesGroup):
    waiting_new_text = State()

POLL_INTERVAL = 2       # секунд между проверками
POLL_MAX_TRIES = 75     # 150 секунд максимум
STREAM_UPDATE_EVERY = 3 # обновлять превью каждые N итераций
EDIT_MIN_INTERVAL = 3.5 # минимум секунд между edit_text (Telegram rate limit)


def _get_default_network(tg_user):
    from aitext.models import NeuralNetwork
    if tg_user.default_network_id:
        try:
            return NeuralNetwork.objects.get(id=tg_user.default_network_id, is_active=True)
        except NeuralNetwork.DoesNotExist:
            pass
    network = NeuralNetwork.objects.filter(provider='openrouter', is_active=True).order_by('order').first()
    if network is None:
        network = NeuralNetwork.objects.filter(is_active=True).order_by('order').first()
    return network


def _ensure_chat(tg_user, network, telegram_chat_id=None):
    """Возвращает активный чат, создавая новый если нужно.

    При наличии active_project чат привязывается к проекту.
    Если активный проект изменился — создаём новый чат.

    telegram_chat_id (#2/#3 повторного ревью): без него push-фолбэк в
    generate_ai_response (aitext/tasks.py) не может доставить текстовый
    ответ, если поллинг хендлера уже сдался (ретрай после провала или
    генерация дольше окна поллинга) — раньше это поле ставилось только для
    медиа-чатов (BUG-H).
    """
    from aitext.models import Chat
    from telegram_bot.models import TelegramChat
    project = tg_user.active_project  # может быть None

    def _with_push_target(chat):
        if telegram_chat_id is None:
            return chat
        s = dict(chat.settings) if isinstance(chat.settings, dict) else {}
        if s.get('telegram_chat_id') != telegram_chat_id:
            s['telegram_chat_id'] = telegram_chat_id
            chat.settings = s
            chat.save(update_fields=['settings'])
        return chat

    tc = TelegramChat.objects.filter(tg_user=tg_user, is_active=True).select_related('chat').first()
    if tc and tc.chat_id:
        chat = tc.chat
        # Если проект у чата не совпадает с active_project — создаём новый чат
        if chat.project_id != (project.id if project else None):
            TelegramChat.objects.filter(tg_user=tg_user, is_active=True).update(is_active=False)
            title = f'Telegram — {project.name}' if project else 'Telegram'
            settings_ = {'telegram_chat_id': telegram_chat_id} if telegram_chat_id is not None else {}
            chat = Chat.objects.create(user=tg_user.user, network=network, title=title, project=project,
                                       settings=settings_)
            TelegramChat.objects.create(tg_user=tg_user, chat=chat, is_active=True)
            return chat
        return _with_push_target(chat)

    title = f'Telegram — {project.name}' if project else 'Telegram'
    settings_ = {'telegram_chat_id': telegram_chat_id} if telegram_chat_id is not None else {}
    chat = Chat.objects.create(user=tg_user.user, network=network, title=title, project=project,
                               settings=settings_)
    if tc:
        tc.chat = chat
        tc.save(update_fields=['chat'])
    else:
        TelegramChat.objects.create(tg_user=tg_user, chat=chat, is_active=True)
    return chat


def _create_messages(chat, user_text, network, system_prompt='', extra_settings=None, attachment=None):
    from aitext.models import Message as AiMessage
    # Персона / системный промт пользователя → на уровень чата (его читает генератор)
    desired = (system_prompt or '').strip()
    current = (chat.settings or {}).get('system_prompt', '') if isinstance(chat.settings, dict) else ''
    if desired != current:
        s = dict(chat.settings) if isinstance(chat.settings, dict) else {}
        if desired:
            s['system_prompt'] = desired
        else:
            s.pop('system_prompt', None)
        chat.settings = s
        chat.save(update_fields=['settings'])
    user_msg = AiMessage.objects.create(chat=chat, role='user', content=user_text)
    if attachment is not None:
        # BUG-G: attachment создаётся в files.py с message=None (файл ещё не
        # привязан к сообщению на момент загрузки) — линкуем здесь тем же
        # приёмом, что и веб-API (api/views/chats.py: attachment_ids →
        # FileAttachment.filter(message__isnull=True).update(message=...)).
        # Без этого user_msg.attachments.all() в tasks.py всегда пуст, и
        # прикреплённый файл/фото в ответ модели никогда не попадает.
        from aitext.models import FileAttachment
        FileAttachment.objects.filter(pk=attachment.pk, message__isnull=True).update(message=user_msg)
        if attachment.extracted_text:
            # Текстовые документы (PDF/DOCX): tasks.py читает extracted-текст
            # либо из Message.extracted_content, либо (для attachment без
            # extracted_text — картинки) через prepare_media_for_ai. Для
            # непустого att.extracted_text вторая ветка сознательно
            # пропускается (та же логика, что в aitext/views.py), поэтому
            # текст нужно продублировать сюда явно.
            user_msg.extracted_content = attachment.extracted_text
            user_msg.save(update_fields=['extracted_content'])
    assistant_msg = AiMessage.objects.create(
        chat=chat, role='assistant',
        status=AiMessage.Status.PENDING,
        content='',
        settings=extra_settings or {},
    )
    return user_msg, assistant_msg


def _get_message_state(msg_id):
    from aitext.models import Message as AiMessage
    return AiMessage.objects.get(id=msg_id)


def _check_balance(user, cost_kopecks):
    return user.has_enough_kopecks(cost_kopecks)


def _get_overage_receipt(msg_id):
    """TOKEN_OVERAGE_BILLING_PLAN.md, Спринт 4 — данные для чека по доплате.

    Возвращает (tokens, settled_kopecks) или None, если доплаты не было.
    Фильтр по settled_kopecks > 0, а не по overage_kopecks: показываем ровно
    то, что реально списано (при dry-run и при неудавшемся settle доплата
    рассчитана, но денег не сняли — чека быть не должно).

    Гонка, о которой стоит знать: generate_ai_response сохраняет статус
    COMPLETED (tasks.py) ДО вызова settle_overage, а поллер ниже просыпается
    каждые POLL_INTERVAL секунд. В редком случае «поллер успел между save и
    settle» строки ещё нет — чек просто не покажется, деньги при этом списаны
    корректно и видны в /account/analytics/ (компенсирующая поверхность из
    §1.1(б) плана). Ретраить/ждать здесь сознательно не стали: цена ошибки —
    отсутствие информационной строки, а не расхождение в деньгах.
    """
    from aitext.models import MessageTokenUsage
    from aitext.token_metering import overage_settle_active

    # Пока доплата выключена/в dry-run, строк с settled_kopecks > 0 не бывает
    # в принципе — не ходим в БД на каждом ответе бота. Тот же приём, что у
    # preflight-клэмпа в api/views/chats.py (Спринт 3).
    if not overage_settle_active():
        return None
    row = (MessageTokenUsage.objects
           .filter(message_id=msg_id, settled_kopecks__gt=0)
           .only('prompt_tokens', 'completion_tokens', 'settled_kopecks')
           .first())
    if row is None:
        return None
    return (row.prompt_tokens or 0) + (row.completion_tokens or 0), row.settled_kopecks


def _charge_text_message(user, assistant_msg, network, cost_kopecks):
    """Pre-charge за текстовое сообщение бота — тот же паттерн, что у веба
    (api/views/chats.py:136-143): списываем ДО генерации, а не полагаемся на
    TEXT_BILLING_ENABLED-фолбэк в aitext/tasks.py (тот срабатывает уже ПОСЛЕ
    успешного ответа и не блокирует бесплатную генерацию при гонке балансов —
    здесь эта гонка закрывается атомарным spend_kopecks до постановки задачи
    в очередь). Возвращает True/False; при False сообщение не отправлено
    в очередь, ассистентское сообщение помечается FAILED.
    """
    from aitext.billing import record_message_billing
    from users.models import UserSpending

    reference = f'chat:{assistant_msg.id}'
    if not user.spend_kopecks(cost_kopecks, type='spend', reference=reference):
        return False
    UserSpending.objects.create(
        user=user, amount=cost_kopecks // 100, amount_kopecks=cost_kopecks,
        description=f"Сообщение в чате с {network.name}",
    )
    record_message_billing(assistant_msg, reference, cost_kopecks)
    return True


get_default_network = sync_to_async(_get_default_network, thread_sensitive=True)
ensure_chat = sync_to_async(_ensure_chat, thread_sensitive=True)
create_messages = sync_to_async(_create_messages, thread_sensitive=True)
get_message_state = sync_to_async(_get_message_state, thread_sensitive=True)
check_balance = sync_to_async(_check_balance, thread_sensitive=True)
get_overage_receipt = sync_to_async(_get_overage_receipt, thread_sensitive=True)
charge_text_message = sync_to_async(_charge_text_message, thread_sensitive=True)


async def process_text(tg_message: Message, tg_user, text: str, attachment=None,
                       skip_billing: bool = False, chat_override=None,
                       voice_reply: bool = False, lang: str = 'ru', org_billing: dict = None):
    """Общий пайплайн: текст → AI → ответ с polling.

    skip_billing=True  — биллинг уже снят на стороне вызывающего (оргбиллинг).
    chat_override      — передать готовый объект Chat (напр., для изолированных групповых чатов).
    voice_reply=True   — дополнительно озвучить ответ (S10: голос-в-голос).
    org_billing        — {'organization_id', 'cost_rub'} от group.py: сумма, уже списанная
                          с баланса организации, чтобы generate_ai_response мог вернуть её
                          при окончательном провале (aitext.billing.refund_org_billing).
    """
    from aitext.tasks import generate_ai_response

    network = await get_default_network(tg_user)
    if not network:
        await tg_message.answer(t('chat.noModels', lang))
        return

    async def _reply_insufficient_balance():
        from core.money import format_money
        if lang == 'ru':
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text='Telegram Stars (XTR)', callback_data='buy_stars')],
                [InlineKeyboardButton(text='Карта / СБП (Robokassa)', callback_data='buy_robokassa')],
                [InlineKeyboardButton(text='Пополнить на сайте', url='https://aineron.ru/account/billing/')],
            ])
        else:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            site_url = getattr(dj_settings, 'SITE_URL', 'https://aineron.net')
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text=t('balance.topUpOnWebsite', lang), url=f'{site_url}/account/billing/')],
            ])
        await tg_message.answer(
            f"<b>{t('chat.insufficientTitle', lang)}</b>\n{DIVIDER}\n"
            f"{t('chat.need', lang)}: <b>{format_money(network.cost_kopecks)}</b>   "
            f"{t('chat.have', lang)}: {format_money(tg_user.user.balance_kopecks)}\n\n"
            f"{t('chat.topUp', lang)}",
            parse_mode='HTML',
            reply_markup=kb,
        )
        await async_log_event(tg_user, 'error', network=network, reason='no_balance')

    if not skip_billing:
        has_balance = await check_balance(tg_user.user, network.cost_kopecks)
        if not has_balance:
            await _reply_insufficient_balance()
            return

    extra_settings = {'skip_star_billing': True} if skip_billing else {}
    if org_billing:
        extra_settings['org_billing'] = org_billing
    chat = chat_override if chat_override is not None else await ensure_chat(tg_user, network, tg_message.chat.id)
    user_msg, assistant_msg = await create_messages(
        chat, text, network, tg_user.system_prompt, extra_settings, attachment,
    )

    if not skip_billing:
        # Pre-charge ДО постановки задачи в очередь (тот же паттерн, что у веба).
        # Провал здесь означает гонку: баланс изменился между проверкой выше и
        # этим моментом (например, два сообщения подряд) — не отправляем в
        # очередь бесплатно, помечаем сообщение неудавшимся и просим пополнить.
        charged = await charge_text_message(tg_user.user, assistant_msg, network, network.cost_kopecks)
        if not charged:
            await tg_user.user.arefresh_from_db()

            def _mark_failed():
                assistant_msg.status = assistant_msg.Status.FAILED
                assistant_msg.error_message = 'insufficient_balance'
                assistant_msg.save(update_fields=['status', 'error_message'])
            await sync_to_async(_mark_failed, thread_sensitive=True)()
            await _reply_insufficient_balance()
            return

    # Найдено при повторном ревью: delay() не был обёрнут (в отличие от
    # images.py) — при недоступном брокере Celery/Redis исключение уходило
    # необработанным до generic except в views.py::_process_update, до
    # показа плейсхолдера пользователю — полная тишина вместо любой
    # обратной связи. process_text — общая точка для chat.py/voice.py/
    # files.py/onboarding.py/prompts_cmd.py/group.py, фикс здесь закрывает
    # все вызывающие стороны разом.
    try:
        generate_ai_response.delay(assistant_msg.id, web_search=getattr(tg_user, 'web_search', False))
    except Exception as e:
        logger.error(f'process_text: не удалось поставить задачу в очередь: {e}')
        await tg_message.answer(
            'Не удалось обработать запрос — попробуйте ещё раз чуть позже.'
            if lang == 'ru' else t('chat.queueError', lang)
        )
        return

    # S1: реакция-статус «запрос принят» на сообщение пользователя
    await set_status_reaction(tg_message.bot, tg_message.chat.id, tg_message.message_id, '👀')

    project = tg_user.active_project
    status_prefix = f'[{project.name}] ' if project else ''
    # S1: нативный стриминг через sendMessageDraft (fallback — edit с троттлингом)
    streamer = stream_draft_or_edit(tg_message, min_edit_interval=EDIT_MIN_INTERVAL)
    await streamer.start(f"{status_prefix}{t('chat.generating', lang)}")

    for i in range(POLL_MAX_TRIES):
        await asyncio.sleep(POLL_INTERVAL)
        try:
            msg = await get_message_state(assistant_msg.id)
        except Exception:
            continue

        if msg.status == 'completed':
            full_text = msg.plain_text or msg.content or ''
            # U6: источники базы знаний под ответом (паритет с вебом)
            kb_sources = getattr(msg, 'kb_sources', None) or []
            if kb_sources:
                names = []
                for s in kb_sources[:4]:
                    n = s.get('filename') if isinstance(s, dict) else str(s)
                    if n and n not in names:
                        names.append(n)
                if names:
                    import html as _html
                    full_text += ('\n\n— Источники: '
                                  + ', '.join(_html.escape(n) for n in names))
            # Спринт 4 плана: чек по доплате за длинный ответ. Дописывается в
            # full_text ДО доставки — тем же способом, что источники выше, а не
            # через card()/отдельное сообщение: full_text уходит либо в
            # telegram_format(), либо в send_rich_or_markdown(), и вставлять
            # туда готовый HTML от card() значило бы получить мангленную
            # разметку на rich-пути. Строка идёт как обычный текст (в ней нет
            # ни markdown-, ни HTML-спецсимволов), DIVIDER — просто «─».
            try:
                _receipt = await get_overage_receipt(msg.id)
                if _receipt:
                    from core.money import format_money
                    _tokens, _settled = _receipt
                    full_text += ('\n\n' + DIVIDER + '\n'
                                  + t('chat.overageReceipt', lang,
                                      tokens=f'{_tokens:,}'.replace(',', ' '),
                                      amount=format_money(_settled)))
            except Exception as _receipt_err:
                # Чек — информационная строка; её отсутствие не должно мешать
                # доставке уже сгенерированного (и оплаченного) ответа.
                logger.warning(f'overage receipt skipped for {msg.id}: {_receipt_err}')
            markup = after_answer_kb(msg.id, copy_code=extract_first_code(full_text), lang=lang)
            delivered = False
            # S1: Rich Messages — таблицы, код, thinking-блоки (за флагом)
            if capabilities.available('rich_messages', tg_message.bot):
                try:
                    await send_rich_or_markdown(
                        tg_message.bot, tg_message.chat.id, full_text, reply_markup=markup,
                    )
                    if streamer.sent is not None:
                        try:
                            await streamer.sent.delete()
                        except Exception:
                            pass
                    delivered = True
                except Exception as e:
                    logger.warning(f'rich delivery failed, fallback to HTML: {e}')
            if not delivered:
                parts = split_message(telegram_format(full_text))
                await streamer.finish(parts, reply_markup=markup)
            # S10: голос-в-голос — озвучиваем ответ на голосовое сообщение
            # (или всегда, если включена настройка «Голосовые ответы»)
            #
            # Найдено при повторном ревью: тот же вызов synthesize_speech,
            # что в voice.py::cb_tts (тариф TTS_COST_KOPECKS), здесь был
            # бесплатным — revenue leak, не вред пользователю. По решению
            # пользователя (не тихий фикс) — тарифицируется так же.
            # Недостаточно средств / любой сбой — просто пропускаем голосовой
            # бонус молча: текстовый ответ уже доставлен выше, это доп. фича,
            # не блокирующая основной путь.
            if voice_reply or tg_user.voice_responses:
                try:
                    from aiogram.types import BufferedInputFile
                    from telegram_bot.handlers.voice import (
                        synthesize_speech, TTS_COST_KOPECKS,
                        has_enough_kopecks, charge_kopecks, refund_kopecks,
                    )
                    if await has_enough_kopecks(tg_user, TTS_COST_KOPECKS):
                        import uuid as _uuid
                        audio = await synthesize_speech(full_text[:700])
                        tts_reference = f'tg-tts:{_uuid.uuid4().hex[:12]}'
                        if await charge_kopecks(tg_user, TTS_COST_KOPECKS, tts_reference):
                            try:
                                await tg_message.answer_voice(
                                    BufferedInputFile(audio, filename='answer.mp3'))
                            except Exception as send_err:
                                logger.warning(f'voice reply delivery failed, refunding: {send_err}')
                                await refund_kopecks(tg_user, TTS_COST_KOPECKS, tts_reference)
                except Exception as e:
                    logger.debug(f'voice reply skipped: {e}')
            await set_status_reaction(tg_message.bot, tg_message.chat.id, tg_message.message_id, None)
            await async_log_event(tg_user, 'message', network=network,
                                  cost_kopecks=network.cost_kopecks)
            return

        elif msg.status == 'failed':
            await streamer.fail(t('chat.error', lang))
            await set_status_reaction(tg_message.bot, tg_message.chat.id, tg_message.message_id, None)
            await async_log_event(tg_user, 'error', network=network, reason='generation_failed')
            return

        # Стриминг частичного ответа (draft или edit с троттлингом внутри стримера)
        if tg_user.streaming and i % STREAM_UPDATE_EVERY == 0:
            partial = (msg.plain_text or msg.content or '').strip()
            if partial:
                await streamer.update(partial)

    await streamer.fail(t('chat.timeout', lang))
    await set_status_reaction(tg_message.bot, tg_message.chat.id, tg_message.message_id, None)
    await async_log_event(tg_user, 'error', network=network, reason='timeout')


@router.message(F.text.startswith('/newchat') | (F.text == 'Новый чат'))
async def cmd_newchat(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    def _reset(u):
        from telegram_bot.models import TelegramChat
        TelegramChat.objects.filter(tg_user=u, is_active=True).update(is_active=False)
    await sync_to_async(_reset, thread_sensitive=True)(tg_user)
    await message.answer(t('chat.newChatStarted', lang), reply_markup=main_reply_kb(lang))


@router.callback_query(F.data == 'newchat')
async def cb_newchat(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    def _reset(u):
        from telegram_bot.models import TelegramChat
        TelegramChat.objects.filter(tg_user=u, is_active=True).update(is_active=False)
    await sync_to_async(_reset, thread_sensitive=True)(tg_user)
    await query.message.answer(t('chat.newChatStarted', lang))
    await query.answer()


@router.callback_query(F.data.startswith('regen:'))
async def cb_regen(query: CallbackQuery, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, query.from_user)
    msg_id = int(query.data.split(':')[1])

    def _get_original_text(m_id, user):
        from aitext.models import Message as AiMsg
        # IDOR: msg_id из callback_data подделываем без владельца — в группе
        # (process_text/after_answer_kb показываются и там, см. group.py)
        # участник Б мог нажать кнопку под сообщением участника А и
        # пересоздать его промт в своём чате. Фильтр по владельцу — тот же
        # паттерн, что уже есть в cb_del_msg ниже (найдено при повторном
        # ревью всего бота).
        msg = AiMsg.objects.filter(id=m_id, chat__user=user).first()
        if msg is None:
            return None
        chat = msg.chat
        user_msg = chat.messages.filter(
            role='user', created_at__lt=msg.created_at
        ).order_by('-created_at').first()
        return user_msg.content if user_msg else None

    get_orig = sync_to_async(_get_original_text, thread_sensitive=True)
    text = await get_orig(msg_id, tg_user.user)
    if text:
        await query.answer(t('chat.regenerating', lang))
        await process_text(query.message, tg_user, text, lang=lang)
    else:
        await query.answer(t('chat.notFoundOriginal', lang))


@router.callback_query(F.data.startswith('react_like:'))
async def cb_react_like(query: CallbackQuery, tg_user=None):
    """👍 — positive reaction: логируем для feedback-петли качества (U6)."""
    lang = resolve_language(tg_user, query.from_user)
    if tg_user is not None:
        await async_log_event(tg_user, 'message', feedback='like',
                              message_id=query.data.split(':')[1])
    await query.answer(t('chat.likeThanks', lang))


@router.callback_query(F.data.startswith('react_dislike:'))
async def cb_react_dislike(query: CallbackQuery, tg_user=None):
    """👎 — negative reaction, regenerate with improvement hint."""
    if tg_user is None:
        await query.answer()
        return
    lang = resolve_language(tg_user, query.from_user)
    msg_id = int(query.data.split(':')[1])

    def _get_original_text(m_id, user):
        from aitext.models import Message as AiMsg
        # IDOR: тот же фикс, что и в cb_regen выше — фильтр по владельцу.
        msg = AiMsg.objects.filter(id=m_id, chat__user=user).first()
        if msg is None:
            return None
        chat = msg.chat
        user_msg = chat.messages.filter(
            role='user', created_at__lt=msg.created_at
        ).order_by('-created_at').first()
        return user_msg.content if user_msg else None

    get_orig = sync_to_async(_get_original_text, thread_sensitive=True)
    # U6: негативный фидбек — сырьё для тюнинга retrieval и выбора моделей
    await async_log_event(tg_user, 'message', feedback='dislike', message_id=msg_id)
    text = await get_orig(msg_id, tg_user.user)
    if text:
        await query.answer(t('chat.reviewing', lang))
        improved_prompt = f"{text}{t('chat.dislikeHint', lang)}"
        await process_text(query.message, tg_user, improved_prompt, lang=lang)
    else:
        await query.answer(t('chat.notFoundOriginal', lang))


@router.callback_query(F.data.startswith('edit_msg:'))
async def cb_edit_msg(query: CallbackQuery, state: FSMContext, tg_user=None):
    """✏️ — ask user for new text, then regenerate."""
    if tg_user is None:
        await query.answer()
        return
    lang = resolve_language(tg_user, query.from_user)
    msg_id = int(query.data.split(':')[1])
    await state.set_state(EditMsgFSM.waiting_new_text)
    await state.update_data(original_msg_id=msg_id, edit_query_msg_id=query.message.message_id)
    await query.answer()
    await query.message.reply(t('chat.sendNewText', lang))


@router.message(EditMsgFSM.waiting_new_text)
async def handle_edit_new_text(message: Message, state: FSMContext, tg_user=None):
    """Receive new text for edit, regenerate."""
    if tg_user is None:
        await state.clear()
        return
    lang = resolve_language(tg_user, message.from_user)
    new_text = (message.text or '').strip()
    if not new_text:
        await message.answer(t('chat.emptyEditText', lang))
        await state.clear()
        return
    await state.clear()
    await process_text(message, tg_user, new_text, lang=lang)


@router.callback_query(F.data.startswith('del_msg:'))
async def cb_del_msg(query: CallbackQuery, tg_user=None):
    """🗑️ — delete the bot's message and mark DB message as deleted."""
    if tg_user is None:
        await query.answer()
        return
    lang = resolve_language(tg_user, query.from_user)
    msg_id = int(query.data.split(':')[1])

    @sync_to_async
    def _mark_deleted(m_id):
        from aitext.models import Message as AiMsg
        try:
            AiMsg.objects.filter(id=m_id, chat__user=tg_user.user).update(
                status=AiMsg.Status.FAILED,
                error_message='[Удалено пользователем]',
            )
        except Exception:
            pass

    await _mark_deleted(msg_id)
    try:
        await query.message.delete()
    except Exception:
        await query.answer(t('chat.deleteFailed', lang))
    else:
        await query.answer(t('chat.deleted', lang))


# StateFilter(None) ОБЯЗАТЕЛЕН: без него catch-all перехватывает текстовые
# шаги FSM всех роутеров, подключённых после chat (tasks/business/mybot и др.),
# и списывает деньги за сообщение, ушедшее в обычный AI-чат.
# F.chat.type == 'private' ОБЯЗАТЕЛЕН: chat.router подключён в bot.py задолго
# до group.router (тот — LAST, "group chat fallback"), а этот catch-all матчит
# любой текст без разбора чата. Без фильтра упоминание/reply боту в ЗАРЕГИСТРИРОВАННОЙ
# на org-биллинг группе никогда не долетало до group.py::handle_group_message —
# списывалось с ЛИЧНОГО баланса участника вместо баланса организации, весь
# механизм org-биллинга был мёртв (найдено при повторном ревью всего бота).
@router.message(F.text & ~F.text.startswith('/'), F.chat.type == 'private', StateFilter(None))
async def handle_text_message(message: Message, tg_user=None):
    if tg_user is None:
        return
    lang = resolve_language(tg_user, message.from_user)
    # S7: сообщение в топике-проекте — свой контекст (Chat) топика
    thread_id = getattr(message, 'message_thread_id', None)
    if thread_id and capabilities.is_enabled('topics'):
        try:
            from telegram_bot.handlers.topics import resolve_topic_chat
            topic_chat = await resolve_topic_chat(tg_user, thread_id)
            if topic_chat is not None:
                await process_text(message, tg_user, message.text, chat_override=topic_chat, lang=lang)
                return
        except Exception as e:
            logger.debug(f'topic routing skipped: {e}')
    # S2: детект интента «задача по расписанию» — предложить создать AI-задачу
    # (не для intl-бота: /task не зарегистрирован там на этой волне)
    if lang == 'ru':
        try:
            from telegram_bot.handlers.tasks_cmd import looks_like_task_intent
            if looks_like_task_intent(message.text):
                from django.core.cache import cache
                from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                set_cached = sync_to_async(cache.set, thread_sensitive=True)
                await set_cached(f'tg_task_intent:{tg_user.telegram_id}', message.text, 600)
                await message.answer(
                    'Похоже на задачу по расписанию. Могу выполнять её автоматически.',
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text='Создать AI-задачу', callback_data='task_intent'),
                    ]]),
                )
        except Exception as e:
            logger.debug(f'task intent detect skipped: {e}')
    await process_text(message, tg_user, message.text, lang=lang)
