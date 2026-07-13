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
from django.conf import settings
from telegram_bot.i18n import t, resolve_language, INTL_LOCALES

logger = logging.getLogger(__name__)
router = Router()

PAGE_SIZE = 5

# Reply-кнопка «Проекты» локализована (см. keyboards.main_reply_kb) — фильтр
# должен матчить как русский текст (aineron.ru), так и переводы menu.projects
# для всех intl-локалей, иначе /projects работает только с русской клавиатурой.
_PROJECTS_BUTTON_TEXTS = {'Проекты'} | {t('menu.projects', code) for code in INTL_LOCALES}


def _project_list_kb(projects: list, current_id: int | None, offset: int, total: int, lang: str = 'ru') -> InlineKeyboardMarkup:
    rows = []
    for p in projects:
        label = f'[{p.name}]' if p.id == current_id else p.name
        rows.append([InlineKeyboardButton(text=label[:40], callback_data=f'proj:select:{p.id}')])

    back_label = 'Назад' if lang == 'ru' else t('projects.back', lang)
    next_label = 'Далее' if lang == 'ru' else t('projects.next', lang)
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text=back_label, callback_data=f'proj:list:{max(0, offset - PAGE_SIZE)}'))
    if offset + PAGE_SIZE < total:
        nav.append(InlineKeyboardButton(text=next_label, callback_data=f'proj:list:{offset + PAGE_SIZE}'))
    if nav:
        rows.append(nav)

    if current_id:
        remove_label = 'Снять проект' if lang == 'ru' else t('projects.removeProjectButton', lang)
        rows.append([InlineKeyboardButton(text=remove_label, callback_data='proj:clear')])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def _project_detail_kb(project_id: int, is_active: bool, lang: str = 'ru') -> InlineKeyboardMarkup:
    buttons = []
    if is_active:
        remove_label = 'Снять проект' if lang == 'ru' else t('projects.removeProjectButton', lang)
        buttons.append([InlineKeyboardButton(text=remove_label, callback_data='proj:clear')])
    else:
        use_label = 'Использовать проект' if lang == 'ru' else t('projects.useProjectButton', lang)
        buttons.append([InlineKeyboardButton(text=use_label, callback_data=f'proj:select:{project_id}')])
    back_label = 'Назад к списку' if lang == 'ru' else t('projects.backToListButton', lang)
    buttons.append([InlineKeyboardButton(text=back_label, callback_data='proj:list:0')])
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


def _format_project_list(projects: list, current_id: int | None, offset: int, total: int, lang: str = 'ru') -> str:
    if lang == 'ru':
        lines = [f'<b>Проекты</b> ({total} шт.)\n']
    else:
        lines = [t('projects.listTitle', lang, total=total) + '\n']
    for p in projects:
        icon = p.icon or ''
        name = f'<b>{p.name}</b>' if p.id == current_id else p.name
        marker = (' (активен)' if lang == 'ru' else f" ({t('projects.activeMarker', lang)})") if p.id == current_id else ''
        lines.append(f'{icon} {name}{marker}')
    if not projects:
        if lang == 'ru':
            lines.append('У тебя пока нет проектов.\nСоздай проект на aineron.ru/projects')
        else:
            site_url = getattr(settings, 'SITE_URL', 'https://aineron.net')
            lines.append(t('projects.noProjects', lang, url=f'{site_url}/projects'))
    return '\n'.join(lines)


async def send_project_list(message: Message | None, query: CallbackQuery | None, tg_user, offset: int = 0, lang: str = 'ru'):
    projects, total = await _get_projects_page(tg_user.user, offset)
    current_id = tg_user.active_project_id
    text = _format_project_list(projects, current_id, offset, total, lang)
    kb = _project_list_kb(projects, current_id, offset, total, lang)

    if query:
        try:
            await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
        except Exception:
            await query.message.answer(text, reply_markup=kb, parse_mode='HTML')
        await query.answer()
    else:
        await message.answer(text, reply_markup=kb, parse_mode='HTML')


@router.message(Command('projects'))
@router.message(F.text.in_(_PROJECTS_BUTTON_TEXTS))
async def cmd_projects(message: Message, tg_user=None):
    lang = resolve_language(tg_user, message.from_user)
    if not tg_user:
        text = ('Привяжи аккаунт через /start чтобы работать с проектами.' if lang == 'ru'
                else t('projects.linkAccountFull', lang))
        await message.answer(text)
        return
    await send_project_list(message, None, tg_user, offset=0, lang=lang)


@router.callback_query(F.data.startswith('proj:list:'))
async def cb_project_list(query: CallbackQuery, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    if not tg_user:
        text = 'Привяжи аккаунт через /start' if lang == 'ru' else t('projects.linkAccountAlert', lang)
        await query.answer(text, show_alert=True)
        return
    offset = int(query.data.split(':')[2])
    await send_project_list(None, query, tg_user, offset=offset, lang=lang)


@router.callback_query(F.data.startswith('proj:select:'))
async def cb_project_select(query: CallbackQuery, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    if not tg_user:
        text = 'Привяжи аккаунт через /start' if lang == 'ru' else t('projects.linkAccountAlert', lang)
        await query.answer(text, show_alert=True)
        return

    project_id = int(query.data.split(':')[2])
    project = await _get_project(tg_user.user, project_id)
    if not project:
        text = 'Проект не найден' if lang == 'ru' else t('projects.notFound', lang)
        await query.answer(text, show_alert=True)
        return

    await _set_active_project(tg_user, project_id)
    # Обновляем local state (FK ID уже записан в БД, но объект tg_user в памяти)
    tg_user.active_project_id = project_id

    file_count = await sync_to_async(project.knowledge_files.filter(status='ready').count)()
    prompt_preview = (project.system_prompt[:120] + '...') if len(project.system_prompt) > 120 else project.system_prompt
    from django.conf import settings as djsettings
    if lang == 'ru':
        tg_upload_hint = ('\nЧтобы добавить файл в базу знаний — просто пришли PDF, TXT, DOC или DOCX.'
                           if getattr(djsettings, 'PROJECT_TG_UPLOAD', False) else '')
        text = (
            f'<b>{project.icon or ""} {project.name}</b> — активирован\n\n'
            + (f'<i>Системный промт:</i>\n{prompt_preview}\n\n' if prompt_preview else '')
            + f'Файлов базы знаний: {file_count}\n\n'
            'Все сообщения теперь идут в контексте этого проекта.\n'
            'Чтобы снять — нажми «Снять проект» или /projects'
            + tg_upload_hint
        )
    else:
        tg_upload_hint = ('\n' + t('projects.addFileHint', lang)
                           if getattr(djsettings, 'PROJECT_TG_UPLOAD', False) else '')
        text = (
            f'<b>{project.icon or ""} {project.name}</b> — {t("projects.activated", lang)}\n\n'
            + (f'<i>{t("projects.systemPromptLabel", lang)}:</i>\n{prompt_preview}\n\n' if prompt_preview else '')
            + f'{t("projects.kbFilesCount", lang)}: {file_count}\n\n'
            + f'{t("projects.allMessagesContext", lang)}\n'
            + t('projects.toDeactivateHint', lang)
            + tg_upload_hint
        )
    kb = _project_detail_kb(project.id, is_active=True, lang=lang)
    try:
        await query.message.edit_text(text, reply_markup=kb, parse_mode='HTML')
    except Exception:
        await query.message.answer(text, reply_markup=kb, parse_mode='HTML')
    answer_text = (f'Проект «{project.name}» активирован' if lang == 'ru'
                   else t('projects.activatedAlert', lang, name=project.name))
    await query.answer(answer_text)


@router.callback_query(F.data == 'proj:clear')
async def cb_project_clear(query: CallbackQuery, tg_user=None):
    lang = resolve_language(tg_user, query.from_user)
    if not tg_user:
        text = 'Привяжи аккаунт через /start' if lang == 'ru' else t('projects.linkAccountAlert', lang)
        await query.answer(text, show_alert=True)
        return

    await _set_active_project(tg_user, None)
    tg_user.active_project_id = None

    answer_text = 'Проект снят' if lang == 'ru' else t('projects.removed', lang)
    await query.answer(answer_text)
    await send_project_list(None, query, tg_user, offset=0, lang=lang)
