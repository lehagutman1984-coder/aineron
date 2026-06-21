"""
Sprint 4.4 — Project Spaces в Telegram боте.

Команды / кнопки:
  /projects            — список проектов пользователя
  Проекты              — reply-кнопка (то же самое)
  [выбор проекта]      — устанавливает TelegramUser.active_project
  [Снять проект]       — убирает active_project (сброс к обычному чату)
  [Информация]         — краткий паспорт проекта (system prompt, файлы)
"""

import logging
from asgiref.sync import sync_to_async
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 5


def _project_list_kb(projects: list, current_id: int | None, offset: int, total: int) -> InlineKeyboardMarkup:
    rows = []
    for p in projects:
        label = f'[{p.name}]' if p.id == current_id else p.name
        rows.append([InlineKeyboardButton(text=label[:40], callback_data=f'proj:select:{p.id}')])

    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text='Назад', callback_data=f'proj:list:{max(0, offset - PAGE_SIZE)}'))
    if offset + PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text='Далее', callback_data=f'proj:list:{offset + PAGE_SIZE}'))
    if nav:
        rows.append(nav)

    if current_id:
        rows.append([InlineKeyboardButton(text='Снять проект', callback_data='proj:clear')])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _project_detail_kb(project_id: int, is_active: bool) -> InlineKeyboardMarkup:
    buttons = []
    if is_active:
        buttons.append([InlineKeyboardButton(text='Снять проект', callback_data='proj:clear')])
    else:
        buttons.append([InlineKeyboardButton(text='Использовать проект', callback_data=f'proj:select:{project_id}')])
    buttons.append([InlineKeyboardButton(text='Назад к списку', callback_data='proj:list:0')])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


@sync_to_async
def _get_projects_page(user, offset: int):
    from aitext.models import Project
    qs = Project.objects.filter(user=user).prefetch_related('knowledge_files').order_by('-updated_at')
    total = qs.count()
    page = list(qs[offset:offset + PAGE_SIZE])
    return page, total


@sync_to_async
def _set_active_project(tg_user, project_id: int | None):
    from aitext.models import Project
    if project_id is None:
        tg_user.active_project = None
    else:
        try:
            proj = Project.objects.get(id=project_id, user=tg_user.user)
            tg_user.active_project = proj
        except Project.DoesNotExist:
            return None
    tg_user.save(update_fields=['active_project'])
    return tg_user.active_project


@sync_to_async
def _get_project(user, project_id: int):
    from aitext.models import Project
    try:
        return Project.objects.prefetch_related('knowledge_files').get(id=project_id, user=user)
    except Project.DoesNotExist:
        return None


def _format_project_list(projects: list, current_id: int | None, offset: int, total: int) -> str:
    lines = [f'<b>Проекты</b> ({total} шт.)\n']
    for p in projects:
        icon = p.icon or ''
        name = f'<b>{p.name}</b>' if p.id == current_id else p.name
        marker = ' (активен)' if p.id == current_id else ''
        lines.append(f'{icon} {name}{marker}')
    if not projects:
        lines.append('У тебя пока нет проектов.\nСоздай проект на aineron.ru/projects')
    return '\n'.join(lines)


async def send_project_list(message: Message | None, query: CallbackQuery | None, tg_user, offset: int = 0):
    projects, total = await _get_projects_page(tg_user.user, offset)
    current_id = tg_user.active_project_id
    text = _format_project_list(projects, current_id, offset, total)
    kb = _project_list_kb(projects, current_id, offset, total)

    if query:
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
        except Exception:
            await query.message.answer(text, reply_markup=kb, parse_mode='HTML')
        await query.answer()
    else:
        await message.answer(text, reply_markup=kb, parse_mode='HTML')


@router.message(Command('projects'))
@router.message(F.text == 'Проекты')
async def cmd_projects(message: Message, tg_user=None):
    if not tg_user:
        await message.answer('Привяжи аккаунт через /start чтобы работать с проектами.')
        return
    await send_project_list(message, None, tg_user, offset=0)


@router.callback_query(F.data.startswith('proj:list:'))
async def cb_project_list(query: CallbackQuery, tg_user=None):
    if not tg_user:
        await query.answer('Привяжи аккаунт через /start', show_alert=True)
        return
    offset = int(query.data.split(':')[2])
    await send_project_list(None, query, tg_user, offset=offset)


@router.callback_query(F.data.startswith('proj:select:'))
async def cb_project_select(query: CallbackQuery, tg_user=None):
    if not tg_user:
        await query.answer('Привяжи аккаунт через /start', show_alert=True)
        return

    project_id = int(query.data.split(':')[2])
    project = await _get_project(tg_user.user, project_id)
    if not project:
        await query.answer('Проект не найден', show_alert=True)
        return

    await _set_active_project(tg_user, project_id)
    # Обновляем local state (FK ID уже записан в БД, но объект tg_user в памяти)
    tg_user.active_project_id = project_id

    file_count = await sync_to_async(project.knowledge_files.filter(status='ready').count)()
    prompt_preview = (project.system_prompt[:120] + '...') if len(project.system_prompt) > 120 else project.system_prompt
    text = (
        f'<b>{project.icon or ""} {project.name}</b> — активирован\n\n'
        + (f'<i>Системный промт:</i>\n{prompt_preview}\n\n' if prompt_preview else '')
        + f'Файлов базы знаний: {file_count}\n\n'
        'Все сообщения теперь идут в контексте этого проекта.\n'
        'Чтобы снять — нажми «Снять проект» или /projects'
    )
    kb = _project_detail_kb(project.id, is_active=True)
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except Exception:
        await query.message.answer(text, reply_markup=kb, parse_mode='HTML')
    await query.answer(f'Проект «{project.name}» активирован')


@router.callback_query(F.data == 'proj:clear')
async def cb_project_clear(query: CallbackQuery, tg_user=None):
    if not tg_user:
        await query.answer('Привяжи аккаунт через /start', show_alert=True)
        return

    await _set_active_project(tg_user, None)
    tg_user.active_project_id = None

    await query.answer('Проект снят')
    await send_project_list(None, query, tg_user, offset=0)
