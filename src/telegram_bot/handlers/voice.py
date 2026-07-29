import io
import logging
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from asgiref.sync import sync_to_async

from telegram_bot.i18n import t, resolve_language

logger = logging.getLogger(__name__)
router = Router()

# BUG-Q (TELEGRAM_SUPREMACY_PLAN_V2.md): та же ставка, что и на вебе
# для тех же вызовов laozhang.ai (api/views/audio.py: ASR_COST_KOPECKS /
# TTS_COST_KOPECKS) — раньше голос в боте не тарифицировался вообще,
# расход у провайдера был всегда, оплата — никогда.
ASR_COST_KOPECKS = 100
TTS_COST_KOPECKS = 100


def _get_laozhang_client():
    from aitext.tasks import get_laozhang_client
    return get_laozhang_client()


async def transcribe_audio(ogg_bytes: bytes) -> str:
    """Отправить аудио в Whisper через laozhang.ai и получить текст."""
    get_client = sync_to_async(_get_laozhang_client, thread_sensitive=True)
    client = await get_client()

    def _transcribe(data):
        response = client.audio.transcriptions.create(
            model='whisper-1',
            file=('audio.ogg', io.BytesIO(data), 'audio/ogg'),
        )
        return response.text

    do_transcribe = sync_to_async(_transcribe, thread_sensitive=True)
    return await do_transcribe(ogg_bytes)


async def synthesize_speech(text: str) -> bytes:
    """Преобразовать текст в аудио через laozhang.ai TTS."""
    get_client = sync_to_async(_get_laozhang_client, thread_sensitive=True)
    client = await get_client()

    def _tts(t):
        response = client.audio.speech.create(
            model='tts-1',
            voice='alloy',
            input=t[:4096],
        )
        return response.content

    do_tts = sync_to_async(_tts, thread_sensitive=True)
    return await do_tts(text)


def _has_enough(tg_user, cost):
    return tg_user.user.has_enough_kopecks(cost)


def _charge(tg_user, cost, reference):
    return tg_user.user.spend_kopecks(cost, type='spend', reference=reference)


def _refund(tg_user, cost, reference):
    return tg_user.user.add_kopecks(cost, type='refund', reference=reference)


has_enough_kopecks = sync_to_async(_has_enough, thread_sensitive=True)
charge_kopecks = sync_to_async(_charge, thread_sensitive=True)
refund_kopecks = sync_to_async(_refund, thread_sensitive=True)


# StateFilter(None) — voice.router подключается раньше нескольких FSM-роутеров
# (img2img, img2video, remind, poll, tasks, business, mybot, channel — см.
# bot.py). Без фильтра голосовое сообщение посреди любого мастера уходило
# сюда и списывалось как обычный чат, не завершая мастер (BUG-N).
# F.chat.type == 'private' — voice.router тоже подключён задолго до group.router
# (LAST в bot.py) и без фильтра ловил голосовые из ЗАРЕГИСТРИРОВАННЫХ на
# org-биллинг групп, списывая с личного баланса отправителя вместо баланса
# организации (тот же класс бага, что и у chat.py:422, найдено при повторном
# ревью всего бота).
@router.message(StateFilter(None), F.chat.type == 'private', F.voice | F.video_note)
async def handle_voice_message(message: Message, tg_user=None, bot=None):
    if tg_user is None:
        return

    lang = resolve_language(tg_user, message.from_user)

    if not await has_enough_kopecks(tg_user, ASR_COST_KOPECKS):
        from core.money import format_money
        price = format_money(ASR_COST_KOPECKS)
        await message.answer(
            f"Недостаточно средств для распознавания голоса ({price})."
            if lang == 'ru' else t('voice.insufficientBalance', lang, price=price)
        )
        return

    status_msg = await message.answer(
        "Распознаю голосовое сообщение..." if lang == 'ru' else t('voice.transcribing', lang)
    )

    try:
        file_id = message.voice.file_id if message.voice else message.video_note.file_id
        tg_file = await bot.get_file(file_id)
        ogg_io = await bot.download_file(tg_file.file_path)
        ogg_bytes = ogg_io.read()

        text = await transcribe_audio(ogg_bytes)

        # Списание ПОСЛЕ успешного распознавания (как на вебе, api/views/audio.py) —
        # неудачные попытки не тарифицируются, возврат не нужен.
        import uuid as _uuid
        # Найдено при повторном ревью: bool-возврат charge_kopecks
        # игнорировался — has_enough_kopecks проверялся РАНЬШЕ (до долгой
        # транскрипции), баланс мог утечь гонкой за это время (параллельный
        # запрос), spend_kopecks тогда тихо не спишет ничего (условный
        # UPDATE), а результат всё равно доставлялся бы бесплатно.
        if not await charge_kopecks(tg_user, ASR_COST_KOPECKS, f'tg-asr:{_uuid.uuid4().hex[:12]}'):
            from core.money import format_money
            price = format_money(ASR_COST_KOPECKS)
            await status_msg.edit_text(
                f"Недостаточно средств для распознавания голоса ({price})." if lang == 'ru'
                else t('voice.insufficientBalance', lang, price=price)
            )
            return

        # Найдено при повторном ревью: edit_text — чисто косметическая подпись
        # («[Голосовое]: …»), но раньше делила try/except с самим переходом в
        # чат-пайплайн ниже — на длинной транскрипции edit_text падал
        # MessageTooLong (Telegram, лимит 4096 симв.), исключение уходило в
        # общий except, process_text НИКОГДА не вызывался: деньги списаны,
        # ответа нет. Теперь сбой подписи не блокирует основной пайплайн.
        label = '[Голосовое]:' if lang == 'ru' else t('voice.label', lang)
        try:
            await status_msg.edit_text(f"<b>{label}</b> {text}", parse_mode='HTML')
        except Exception as label_err:
            logger.warning(f'voice label edit failed (non-fatal): {label_err}')

        # Передаём в обычный чат-пайплайн; S10 — ответ голосом на голосовое
        from telegram_bot.handlers.chat import process_text
        await process_text(message, tg_user, text, voice_reply=True, lang=lang)

    except Exception as e:
        logger.exception(f'Voice transcription error: {e}')
        await status_msg.edit_text(
            "Не удалось распознать голосовое. Попробуй ещё раз." if lang == 'ru' else t('voice.recognitionFailed', lang)
        )


@router.callback_query(F.data.startswith('tts:'))
async def cb_tts(query: CallbackQuery, tg_user=None, bot=None):
    if tg_user is None:
        return

    lang = resolve_language(tg_user, query.from_user)
    msg_id = int(query.data.split(':')[1])

    def _get_msg_text(m_id, user):
        from aitext.models import Message as AiMsg
        # IDOR: msg_id из callback_data без владельца — озвучивал чужие
        # сообщения (в группе кнопка видна всем, см. chat.py:295 cb_regen —
        # тот же класс, тот же фикс: фильтр по владельцу).
        msg = AiMsg.objects.filter(id=m_id, chat__user=user).first()
        if msg is None:
            return ''
        return msg.plain_text or msg.content or ''

    get_text = sync_to_async(_get_msg_text, thread_sensitive=True)

    if not await has_enough_kopecks(tg_user, TTS_COST_KOPECKS):
        from core.money import format_money
        price = format_money(TTS_COST_KOPECKS)
        await query.answer(
            f"Недостаточно средств для озвучивания ({price})."
            if lang == 'ru' else t('voice.insufficientBalance', lang, price=price),
            show_alert=True,
        )
        return

    await query.answer("Синтезирую речь..." if lang == 'ru' else t('voice.synthesizing', lang))
    try:
        text = await get_text(msg_id, tg_user.user)
        if not text:
            await query.message.answer(
                "Нет текста для озвучивания." if lang == 'ru' else t('voice.noTextToSpeak', lang)
            )
            return

        audio_bytes = await synthesize_speech(text)

        # Списание ПОСЛЕ успешного синтеза — неудачные попытки не тарифицируются.
        import uuid as _uuid
        tts_reference = f'tg-tts:{_uuid.uuid4().hex[:12]}'
        # Найдено при повторном ревью: bool-возврат charge_kopecks
        # игнорировался — has_enough_kopecks проверялся ДО синтеза, баланс
        # мог утечь гонкой за это время; без проверки результат доставлялся
        # бы бесплатно.
        if not await charge_kopecks(tg_user, TTS_COST_KOPECKS, tts_reference):
            from core.money import format_money
            price = format_money(TTS_COST_KOPECKS)
            await query.message.answer(
                f"Недостаточно средств для озвучивания ({price})." if lang == 'ru'
                else t('voice.insufficientBalance', lang, price=price)
            )
            return

        audio_file = BufferedInputFile(audio_bytes, filename='response.mp3')
        # Найдено при повторном ревью: если answer_voice падает ПОСЛЕ списания
        # (файл великоват, сетевой сбой) — деньги были списаны за синтез, но
        # ничего не доставлено, возврата не было. Тот же reference — refund
        # идёт по той же записи, что и списание (established pattern).
        try:
            await query.message.answer_voice(audio_file)
        except Exception as send_err:
            logger.warning(f'TTS delivery failed after charge, refunding: {send_err}')
            await refund_kopecks(tg_user, TTS_COST_KOPECKS, tts_reference)
            raise

    except Exception as e:
        logger.exception(f'TTS error: {e}')
        await query.message.answer(
            "Ошибка синтеза речи. Попробуй позже." if lang == 'ru' else t('voice.synthesisError', lang)
        )
