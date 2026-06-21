import io
import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
router = Router()


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


@router.message(F.voice | F.video_note)
async def handle_voice_message(message: Message, tg_user=None, bot=None):
    if tg_user is None:
        return

    status_msg = await message.answer("Распознаю голосовое сообщение...")

    try:
        file_id = message.voice.file_id if message.voice else message.video_note.file_id
        tg_file = await bot.get_file(file_id)
        ogg_io = await bot.download_file(tg_file.file_path)
        ogg_bytes = ogg_io.read()

        text = await transcribe_audio(ogg_bytes)

        await status_msg.edit_text(f"<b>[Голосовое]:</b> {text}", parse_mode='HTML')

        # Передаём в обычный чат-пайплайн
        from telegram_bot.handlers.chat import process_text
        await process_text(message, tg_user, text)

    except Exception as e:
        logger.exception(f'Voice transcription error: {e}')
        await status_msg.edit_text("Не удалось распознать голосовое. Попробуй ещё раз.")


@router.callback_query(F.data.startswith('tts:'))
async def cb_tts(query: CallbackQuery, tg_user=None, bot=None):
    if tg_user is None:
        return

    msg_id = int(query.data.split(':')[1])

    def _get_msg_text(m_id):
        from aitext.models import Message as AiMsg
        msg = AiMsg.objects.get(id=m_id)
        return msg.plain_text or msg.content or ''

    get_text = sync_to_async(_get_msg_text, thread_sensitive=True)

    await query.answer("Синтезирую речь...")
    try:
        text = await get_text(msg_id)
        if not text:
            await query.message.answer("Нет текста для озвучивания.")
            return

        audio_bytes = await synthesize_speech(text)
        audio_file = BufferedInputFile(audio_bytes, filename='response.mp3')
        await query.message.answer_voice(audio_file)

    except Exception as e:
        logger.exception(f'TTS error: {e}')
        await query.message.answer("Ошибка синтеза речи. Попробуй позже.")
