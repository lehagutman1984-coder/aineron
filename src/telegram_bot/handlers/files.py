import logging
import os
import tempfile
import uuid
from aiogram import Router, F
from aiogram.types import Message
from asgiref.sync import sync_to_async

logger = logging.getLogger(__name__)
router = Router()
MAX_FILE_SIZE = 20 * 1024 * 1024  # 20MB
ALLOWED_EXTS = {'.pdf', '.txt', '.doc', '.docx'}


def _save_file_to_storage(file_bytes: bytes, original_name: str, mime_type: str, user, media_type: str):
    """Save file to Django storage and create FileAttachment record (no message link)."""
    from django.core.files.storage import default_storage
    from django.core.files.base import ContentFile
    from aitext.models import FileAttachment

    ext = os.path.splitext(original_name)[1].lower() or '.bin'
    storage_path = f'attachments/{user.id}/tg/{uuid.uuid4()}{ext}'
    file_path = default_storage.save(storage_path, ContentFile(file_bytes, name=storage_path))

    att = FileAttachment.objects.create(
        message=None,
        filename=original_name,
        file_path=file_path,
        file_size=len(file_bytes),
        mime_type=mime_type,
        media_type=media_type,
        source='uploaded',
    )
    return att


def _extract_text(att):
    """Try to extract text from file attachment."""
    try:
        from django.core.files.storage import default_storage
        full_path = default_storage.path(att.file_path)
        from aitext.file_utils import extract_text_from_file
        text = extract_text_from_file(full_path, att.filename)
        if text:
            att.extracted_text = text[:8000]
            att.save(update_fields=['extracted_text'])
        return text or ''
    except Exception as e:
        logger.warning(f'Text extraction failed for {att.filename}: {e}')
        return ''


_save_file_async = sync_to_async(_save_file_to_storage, thread_sensitive=True)
_extract_text_async = sync_to_async(_extract_text, thread_sensitive=True)


async def _download_and_save(bot, file_id: str, original_name: str, mime_type: str, user, media_type: str):
    """Download file from Telegram and save to storage."""
    file_info = await bot.get_file(file_id)
    ext = os.path.splitext(original_name)[1].lower() or '.bin'
    with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
        tmp_path = tmp.name
    try:
        await bot.download_file(file_info.file_path, destination=tmp_path)
        with open(tmp_path, 'rb') as f:
            file_bytes = f.read()
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return await _save_file_async(file_bytes, original_name, mime_type, user, media_type)


@router.message(F.photo)
async def handle_photo(message: Message, tg_user=None):
    if tg_user is None:
        return
    caption = (message.caption or '').strip()
    prompt = caption if caption else 'Опиши это изображение подробно'

    status = await message.answer('Анализирую изображение...')
    try:
        photo = message.photo[-1]
        att = await _download_and_save(
            message.bot, photo.file_id, 'photo.jpg', 'image/jpeg',
            tg_user.user, 'image',
        )
        from telegram_bot.handlers.chat import process_text
        # Build user text with file reference
        full_text = f'{prompt}\n[Изображение прикреплено: {att.id}]'
        await process_text(message, tg_user, prompt, attachment=att)
        try:
            await status.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f'Photo handler error: {e}')
        await status.edit_text('Не удалось обработать изображение. Попробуй ещё раз.')


@router.message(F.document)
async def handle_document(message: Message, tg_user=None):
    if tg_user is None:
        return
    doc = message.document
    caption = (message.caption or '').strip()
    name = doc.file_name or 'document'
    ext = os.path.splitext(name)[1].lower()

    if ext not in ALLOWED_EXTS:
        await message.answer(f'Поддерживаются: PDF, TXT, DOC, DOCX. Получен: {ext or "без расширения"}')
        return
    if doc.file_size and doc.file_size > MAX_FILE_SIZE:
        await message.answer('Файл слишком большой (макс. 20 МБ).')
        return

    status = await message.answer(f'Читаю документ {name}...')
    try:
        media_type = 'pdf' if ext == '.pdf' else 'other'
        att = await _download_and_save(
            message.bot, doc.file_id, name, doc.mime_type or 'application/octet-stream',
            tg_user.user, media_type,
        )
        await _extract_text_async(att)

        prompt = caption if caption else f'Проанализируй содержимое документа "{name}"'
        from telegram_bot.handlers.chat import process_text
        await process_text(message, tg_user, prompt, attachment=att)
        try:
            await status.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f'Document handler error: {e}')
        await status.edit_text('Не удалось обработать файл. Попробуй ещё раз.')
