import logging
import os
import tempfile
import uuid
from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
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


# StateFilter(None): роутер подключён в bot.py раньше FSM-роутеров (img2img,
# img2video, admin-рассылка) — без фильтра он перехватывал фото, отправленные
# внутри FSM-сценария, и отдавал их в текстовый чат вместо нужного шага.
@router.message(F.photo, StateFilter(None))
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


@router.message(F.document, StateFilter(None))
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

    # Sprint 5.6: if user has an active project, offer to save to knowledge base
    from django.conf import settings as djsettings
    if getattr(djsettings, 'PROJECT_TG_UPLOAD', False) and tg_user.active_project_id:
        active_proj_name = await _get_project_name(tg_user.active_project_id)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f'В базу знаний «{active_proj_name[:25]}»',
                    callback_data=f'tgupload:kb:{tg_user.active_project_id}:{doc.file_id}:{name[:60]}',
                ),
            ],
            [
                InlineKeyboardButton(
                    text='В чат (без сохранения)',
                    callback_data=f'tgupload:chat:{doc.file_id}:{name[:60]}',
                ),
            ],
        ])
        await message.answer(
            f'Куда отправить <b>{name}</b>?',
            reply_markup=kb,
            parse_mode='HTML',
        )
        return

    await _process_document_to_chat(message, tg_user, doc, name, ext, caption)


async def _process_document_to_chat(message: Message, tg_user, doc, name: str, ext: str, caption: str):
    """Download document and send to chat as attachment."""
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


@sync_to_async
def _get_project_name(project_id: int) -> str:
    from aitext.models import Project
    try:
        return Project.objects.values_list('name', flat=True).get(id=project_id)
    except Project.DoesNotExist:
        return 'Проект'


@sync_to_async
def _save_to_project_kb(project_id: int, user, file_bytes: bytes, filename: str) -> tuple[bool, str]:
    """Save file bytes as ProjectFile and trigger processing. Returns (ok, message)."""
    from aitext.models import Project, ProjectFile
    from django.core.files.base import ContentFile

    MAX_FILES = 20
    try:
        project = Project.objects.get(id=project_id)
    except Project.DoesNotExist:
        return False, 'Проект не найден'

    if project.knowledge_files.count() >= MAX_FILES:
        return False, f'В проекте уже {MAX_FILES} файлов (максимум)'

    ext = os.path.splitext(filename)[1].lower()
    if ext == '.pdf':
        file_type = 'pdf'
    elif ext in ('.doc', '.docx'):
        file_type = 'doc'
    elif ext == '.txt':
        file_type = 'text'
    else:
        file_type = 'other'

    pf = ProjectFile.objects.create(
        project=project,
        filename=filename,
        file=ContentFile(file_bytes, name=filename),
        file_size=len(file_bytes),
        file_type=file_type,
        status='processing',
        source='upload',
    )
    from aitext.tasks import process_project_file
    process_project_file.delay(pf.id)
    return True, project.name


@router.callback_query(F.data.startswith('tgupload:kb:'))
async def cb_upload_to_kb(query: CallbackQuery, tg_user=None):
    """Download file from Telegram and save to project knowledge base."""
    if tg_user is None:
        await query.answer('Привяжи аккаунт через /start', show_alert=True)
        return

    # callback_data: tgupload:kb:{project_id}:{file_id}:{filename}
    parts = query.data.split(':', 4)
    if len(parts) < 5:
        await query.answer('Ошибка', show_alert=True)
        return

    project_id = int(parts[2])
    file_id = parts[3]
    filename = parts[4]
    ext = os.path.splitext(filename)[1].lower()

    await query.answer()
    status_msg = await query.message.edit_text(f'Загружаю {filename} в базу знаний...')

    try:
        file_info = await query.bot.get_file(file_id)
        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = tmp.name
        try:
            await query.bot.download_file(file_info.file_path, destination=tmp_path)
            with open(tmp_path, 'rb') as f:
                file_bytes = f.read()
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        ok, msg = await _save_to_project_kb(project_id, tg_user.user, file_bytes, filename)
        if ok:
            await status_msg.edit_text(
                f'Файл <b>{filename}</b> добавлен в базу знаний проекта «{msg}».\n'
                'Обработка займёт несколько секунд.',
                parse_mode='HTML',
            )
        else:
            await status_msg.edit_text(f'Не удалось добавить файл: {msg}')
    except Exception as e:
        logger.error(f'tgupload:kb error: {e}')
        await status_msg.edit_text('Ошибка загрузки файла. Попробуй ещё раз.')


@router.callback_query(F.data.startswith('tgupload:chat:'))
async def cb_upload_to_chat(query: CallbackQuery, tg_user=None):
    """User chose to send file to chat instead of KB."""
    if tg_user is None:
        await query.answer('Привяжи аккаунт через /start', show_alert=True)
        return

    parts = query.data.split(':', 3)
    if len(parts) < 4:
        await query.answer('Ошибка', show_alert=True)
        return

    file_id = parts[2]
    filename = parts[3]
    ext = os.path.splitext(filename)[1].lower()

    await query.answer()
    try:
        await query.message.delete()
    except Exception:
        pass

    # Build a synthetic document-like object and process normally
    media_type = 'pdf' if ext == '.pdf' else 'other'
    status = await query.message.answer(f'Читаю документ {filename}...')
    try:
        att = await _download_and_save(
            query.bot, file_id, filename, 'application/octet-stream',
            tg_user.user, media_type,
        )
        await _extract_text_async(att)
        prompt = f'Проанализируй содержимое документа "{filename}"'
        from telegram_bot.handlers.chat import process_text
        await process_text(query.message, tg_user, prompt, attachment=att)
        try:
            await status.delete()
        except Exception:
            pass
    except Exception as e:
        logger.error(f'tgupload:chat error: {e}')
        await status.edit_text('Не удалось обработать файл. Попробуй ещё раз.')
