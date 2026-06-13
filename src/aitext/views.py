import json
import logging
from django.core.paginator import Paginator
from django.shortcuts import render, get_object_or_404
from users.models import Tariff, LegalDocument  # если нужно
from django.urls import reverse
from django.core.files.storage import default_storage
from django.db.models import Count
from django.db.models import Q
from .models import FAQ
from .models import Chat
from blog.models import Post
from users.models import UserSpending
from django.utils import timezone
from django.db import transaction
from .file_utils import save_uploaded_file, validate_file
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from .models import Category, NeuralNetwork, Chat, Message, NeuralNetworkDailyUsage, GeneratedImage
from .tasks import generate_ai_response

logger = logging.getLogger(__name__)

def get_faqs_for_page(neural_network_slug=None):
    """Возвращает список FAQ в зависимости от страницы"""
    if neural_network_slug:
        return FAQ.objects.filter(
            Q(show_everywhere=True) | Q(neural_network__slug=neural_network_slug)
        ).distinct().order_by('order')
    else:
        return FAQ.objects.filter(
            Q(show_everywhere=True) | Q(show_on_main=True)
        ).distinct().order_by('order')


def get_networks_by_category(request):
    categories = Category.objects.all().prefetch_related('networks')
    default_network = NeuralNetwork.objects.filter(is_default=True, is_active=True).first()
    data = []
    for cat in categories:
        networks = cat.networks.filter(is_active=True).annotate(
            chats_count=Count('chats')
        )
        data.append({
            'id': cat.id,
            'name': cat.name,
            'slug': cat.slug,
            'icon': cat.icon,
            'networks': [{
                'id': n.id,
                'name': n.name,
                'slug': n.slug,
                'avatar': n.get_avatar(),
                'description': n.description,
                'cost': n.cost_per_message,
                'unlimited': n.unlimited,
                'messages_limit': n.messages_limit,
                'tariff_ids': [t.id for t in n.tariffs.all()],
                'chats_count': n.chats_count,
                'is_popular': n.is_popular
            } for n in networks]
        })
    return JsonResponse({
        'success': True,
        'categories': data,
        'default_model': {
            'slug': default_network.slug,
            'name': default_network.name,
            'avatar': default_network.get_avatar()
        } if default_network else None
    })


def chat_landing(request, network_slug):
    network = get_object_or_404(NeuralNetwork, slug=network_slug, is_active=True)

    user_chats = []
    if request.user.is_authenticated:
        user_chats = Chat.objects.filter(user=request.user).select_related('network').prefetch_related(
            'messages').order_by('-updated_at')[:15]

    # Популярные модели
    popular_networks = NeuralNetwork.objects.filter(is_active=True, is_popular=True).order_by('order')[:7]

    # Статьи блога
    related_posts = Post.objects.filter(
        is_published=True,
        neural_networks=network
    ).order_by('-published_at')[:3]

    # Пробный тариф (если у пользователя нет платной подписки)
    trial_tariff = None
    if request.user.is_authenticated and (not request.user.active_subscription or request.user.tariff.is_free):
        trial_tariff = Tariff.objects.filter(is_trial=True, is_active=True).first()

    # Поддерживаемые типы файлов
    file_capabilities = {
        'archive': network.handle_archive,
        'text_files': network.handle_text_files,
        'photo': network.handle_photo,
        'video': network.handle_video,
    }
    file_capabilities_json = json.dumps(file_capabilities)

    # Конфигурация для fal.ai
    config_json = None
    if network.provider == 'fal-ai' and network.config_json:
        config_json = json.dumps(network.config_json)

    # FAQ для страницы нейросети
    faqs = get_faqs_for_page(network_slug)

    # URL для юридических документов (мета-теги)
    terms_url = reverse('users_pages:terms_of_service')
    privacy_url = reverse('users_pages:privacy_policy')

    # Тарифы, дающие безлимит для этой нейросети
    unlimited_tariffs = network.tariffs.all() if network.unlimited else []

    return render(request, 'neuro/chatland.html', {
        'network': network,
        'user_chats': user_chats,
        'current_chat_id': None,
        'file_capabilities_json': file_capabilities_json,
        'config_json': config_json,
        'related_posts': related_posts,
        'popular_networks': popular_networks,
        'trial_tariff': trial_tariff,
        'terms_url': terms_url,
        'privacy_url': privacy_url,
        'faqs': faqs,
        'unlimited_tariffs': unlimited_tariffs,
    })

@login_required
@csrf_exempt
@require_POST
def create_chat(request):
    """
    Создание чата и первого сообщения пользователя (с возможностью прикрепления файлов)
    """
    try:
        data = json.loads(request.body)
        network_slug = data.get('network_slug')
        message_text = data.get('message', '').strip()
        files = data.get('files', [])
        settings = data.get('settings', {})

        if not network_slug:
            return JsonResponse({'success': False, 'message': 'Не указана нейросеть'})
        if not message_text and not files:
            return JsonResponse({'success': False, 'message': 'Нет текста или файлов'})

        network = get_object_or_404(NeuralNetwork, slug=network_slug, is_active=True)
        cost = network.cost_per_message
        deduct_stars = True

        # ========== ЛОГИКА БЕСПЛАТНЫХ СООБЩЕНИЙ ==========
        if network.unlimited and network.tariffs.filter(id=request.user.tariff.id).exists() and network.messages_limit > 0:
            today = timezone.now().date()
            usage, created = NeuralNetworkDailyUsage.objects.get_or_create(
                user=request.user,
                network=network,
                date=today,
                defaults={'count': 0}
            )
            if usage.count < network.messages_limit:
                deduct_stars = False
                usage.count += 1
                usage.save()
                logger.info(f"Бесплатное сообщение для {request.user.email} в {network.name} ({usage.count}/{network.messages_limit})")

        # Проверка баланса для fal.ai (списание в Celery, но проверяем сейчас)
        if deduct_stars and request.user.pages_count < cost:
            return JsonResponse({
                'success': False,
                'message': f'Недостаточно звёзд. Нужно {cost} зв., у вас {request.user.pages_count} зв.'
            })

        # Создаём чат с настройками
        chat = Chat.objects.create(
            user=request.user,
            network=network,
            title=message_text[:50] if message_text else f"{network.name} - {timezone.now().strftime('%d.%m.%Y %H:%M')}",
            settings=settings
        )

        # Сообщение пользователя
        user_message = Message.objects.create(
            chat=chat,
            role='user',
            content=message_text,
            files=files,
            status=Message.Status.COMPLETED,
            settings=settings
        )

        # Сохраняем файлы и извлекаем текст
        extracted_texts = []
        for file_data in files:
            is_valid, error, _ = validate_file(file_data)
            if not is_valid:
                logger.warning(f"Файл {file_data.get('name')} не прошёл валидацию: {error}")
                continue
            attachment = save_uploaded_file(file_data, user_message)
            if attachment and attachment.extracted_text:
                extracted_texts.append(f"Содержимое файла {attachment.filename}:\n{attachment.extracted_text}")

        if extracted_texts:
            user_message.extracted_content = "\n\n".join(extracted_texts)
            user_message.save(update_fields=['extracted_content'])
            logger.info(f"Добавлен извлечённый текст из файлов в extracted_content сообщения {user_message.id}")

        # Сообщение ассистента
        assistant_message = Message.objects.create(
            chat=chat,
            role='assistant',
            content='',
            status=Message.Status.PENDING
        )

        # ========== СПИСАНИЕ ЗВЁЗД (только для текстовых моделей) ==========
        # Для моделей изображений/видео списание происходит в задаче Celery
        if network.provider != 'fal-ai' and deduct_stars:
            request.user.spend_pages(cost)
            UserSpending.objects.create(
                user=request.user,
                amount=cost,
                description=f"Сообщение в чате с {network.name}"
            )

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(assistant_message.id)

        return JsonResponse({
            'success': True,
            'chat_id': chat.id,
            'new_balance': request.user.pages_count
        })

    except Exception as e:
        logger.error(f"Ошибка в create_chat: {e}")
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def chat_detail(request, chat_id):
    """Страница чата с нейросетью"""
    chat = get_object_or_404(Chat, id=chat_id, user=request.user)
    network = chat.network
    user = request.user
    cost = network.cost_per_message
    free_info = None
    config_json = None

    # Проверяем, доступны ли бесплатные сообщения
    if network.unlimited and network.tariffs.filter(id=user.tariff.id).exists() and network.messages_limit > 0:
        today = timezone.now().date()
        usage, _ = NeuralNetworkDailyUsage.objects.get_or_create(
            user=user,
            network=network,
            date=today,
            defaults={'count': 0}
        )
        remaining = max(0, network.messages_limit - usage.count)
        free_info = {
            'limit': network.messages_limit,
            'remaining': remaining,
            'message': f"Безлимит по вашему тарифу - не более {network.messages_limit} сообщений в день! (Осталось {remaining})"
        }

    # Проверяем, есть ли у пользователя платная подписка
    has_paid_subscription = False
    if user.is_authenticated and user.active_subscription and not user.tariff.is_free:
        has_paid_subscription = True

    # Получаем последние 15 чатов для сайдбара
    user_chats = Chat.objects.filter(user=user).select_related('network').prefetch_related('messages').order_by('-updated_at')[:15]

    # Поддерживаемые типы файлов
    file_capabilities = {
        'archive': network.handle_archive,
        'text_files': network.handle_text_files,
        'photo': network.handle_photo,
        'video': network.handle_video,
    }
    file_capabilities_json = json.dumps(file_capabilities)

    # Конфигурация для fal.ai
    if network.provider == 'fal-ai' and network.config_json:
        config_json = json.dumps(network.config_json)

    # Настройки чата
    chat_settings_json = json.dumps(chat.settings) if chat.settings else '{}'

    return render(request, 'neuro/chat.html', {
        'network': network,
        'chat': chat,
        'messages': chat.messages.all(),
        'user_chats': user_chats,
        'current_chat_id': chat.id,
        'cost': cost,
        'free_info': free_info,
        'file_capabilities_json': file_capabilities_json,
        'config_json': config_json,
        'chat_settings_json': chat_settings_json,
        'has_paid_subscription': has_paid_subscription,
    })


@login_required
@csrf_exempt
@require_POST
def send_message(request, chat_id):
    """API: отправить сообщение в чат и поставить задачу на генерацию ответа"""
    try:
        data = json.loads(request.body)
        message_text = data.get('message', '').strip()
        files = data.get('files', [])
        settings = data.get('settings', {})

        if not message_text and not files:
            return JsonResponse({'success': False, 'message': 'Нет текста или файлов'})

        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        network = chat.network
        cost = network.cost_per_message
        deduct_stars = True

        # ========== ЛОГИКА БЕСПЛАТНЫХ СООБЩЕНИЙ ==========
        today = timezone.now().date()
        if network.unlimited and network.tariffs.filter(id=request.user.tariff.id).exists() and network.messages_limit > 0:
            usage, created = NeuralNetworkDailyUsage.objects.get_or_create(
                user=request.user,
                network=network,
                date=today,
                defaults={'count': 0}
            )
            if usage.count < network.messages_limit:
                deduct_stars = False
                usage.count += 1
                usage.save()
                logger.info(f"Бесплатное сообщение для {request.user.email} в {network.name} ({usage.count}/{network.messages_limit})")
            else:
                logger.info(f"Лимит бесплатных сообщений исчерпан для {request.user.email} в {network.name}")

        # Проверка баланса для fal.ai (списание в Celery, но проверяем сейчас)
        if deduct_stars and request.user.pages_count < cost:
            return JsonResponse({
                'success': False,
                'message': f'Недостаточно звёзд. Нужно {cost} зв., у вас {request.user.pages_count} зв.'
            })

        # Обновляем настройки чата, если они отличаются
        if chat.settings != settings:
            chat.settings = settings
            chat.save(update_fields=['settings'])

        # ========== СОЗДАНИЕ СООБЩЕНИЯ ПОЛЬЗОВАТЕЛЯ ==========
        user_message = Message.objects.create(
            chat=chat,
            role='user',
            content=message_text,
            files=files,
            status=Message.Status.COMPLETED,
            settings=settings
        )

        # ========== СОХРАНЕНИЕ ПРИКРЕПЛЁННЫХ ФАЙЛОВ ==========
        extracted_texts = []
        for file_data in files:
            is_valid, error, _ = validate_file(file_data)
            if not is_valid:
                logger.warning(f"Файл {file_data.get('name')} не прошёл валидацию: {error}")
                continue
            attachment = save_uploaded_file(file_data, user_message)
            if attachment and attachment.extracted_text:
                extracted_texts.append(f"Содержимое файла {attachment.filename}:\n{attachment.extracted_text}")

        if extracted_texts:
            user_message.extracted_content = "\n\n".join(extracted_texts)
            user_message.save(update_fields=['extracted_content'])
            logger.info(f"Добавлен извлечённый текст из файлов в extracted_content сообщения {user_message.id}")

        # ========== СОЗДАНИЕ СООБЩЕНИЯ АССИСТЕНТА ==========
        assistant_message = Message.objects.create(
            chat=chat,
            role='assistant',
            content='',
            status=Message.Status.PENDING
        )

        # ========== СПИСАНИЕ ЗВЁЗД (только для текстовых моделей) ==========
        # Для моделей изображений/видео списание происходит в задаче Celery
        if network.provider != 'fal-ai' and deduct_stars:
            request.user.spend_pages(cost)
            UserSpending.objects.create(
                user=request.user,
                amount=cost,
                description=f"Сообщение в чате с {network.name}"
            )

        # ========== ОБНОВЛЕНИЕ ЧАТА ==========
        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        if not chat.title and message_text:
            chat.title = message_text[:50] + ('...' if len(message_text) > 50 else '')
            chat.save(update_fields=['title'])

        # ========== ЗАПУСК ЗАДАЧИ CELERY ==========
        generate_ai_response.delay(assistant_message.id)

        return JsonResponse({
            'success': True,
            'user_message': {
                'id': user_message.id,
                'content': user_message.content,
                'files': user_message.files,
                'created_at': user_message.created_at.strftime('%H:%M')
            },
            'assistant_message_id': assistant_message.id,
            'new_balance': request.user.pages_count,
            'cost': cost,
            'free_message': not deduct_stars
        })

    except Exception as e:
        logger.error(f"Ошибка в send_message: {e}")
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
def message_status(request, message_id):
    try:
        message = get_object_or_404(Message, id=message_id, chat__user=request.user)
        return JsonResponse({
            'success': True,
            'status': message.status,
            'content': message.content if message.status == Message.Status.COMPLETED else None,
            'plain_text': message.plain_text if message.status == Message.Status.COMPLETED else None,
            'error': message.error_message if message.status == Message.Status.FAILED else None
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@csrf_exempt
@require_POST
def delete_chat(request, chat_id):
    """Удаление чата пользователя"""
    try:
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        chat.delete()
        return JsonResponse({'success': True, 'message': 'Чат удалён'})
    except Exception as e:
        logger.error(f"Ошибка удаления чата {chat_id}: {e}")
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def user_chats(request):
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 15))

        chats = Chat.objects.filter(user=request.user).select_related('network').prefetch_related('messages').order_by('-updated_at')
        paginator = Paginator(chats, per_page)

        if page > paginator.num_pages:
            return JsonResponse({'success': True, 'chats': [], 'has_next': False})

        page_obj = paginator.page(page)
        chats_data = []
        for chat in page_obj:
            last_message = chat.messages.order_by('-created_at').first()
            if not last_message:
                preview = "Нет сообщений"
            elif last_message.role == 'assistant' and last_message.status == 'pending':
                preview = "Печатает..."
            else:
                content = last_message.content or "Нет сообщений"
                if len(content) > 30:
                    preview = content[:27] + "..."
                else:
                    preview = content

            chats_data.append({
                'id': chat.id,
                'network_name': chat.network.name,
                'network_avatar': chat.network.get_avatar(),
                'title': chat.title or chat.network.name,
                'preview': preview,
                'updated_at': chat.updated_at.isoformat()
            })

        return JsonResponse({
            'success': True,
            'chats': chats_data,
            'has_next': page < paginator.num_pages,
            'current_page': page,
            'total_pages': paginator.num_pages
        })
    except Exception as e:
        logger.error(f"Ошибка получения чатов: {e}")
        return JsonResponse({'success': False, 'message': str(e)})


def catalog(request):
    """Страница каталога нейросетей (доступна всем)"""
    user_chats = []
    if request.user.is_authenticated:
        user_chats = Chat.objects.filter(user=request.user).select_related('network').prefetch_related('messages').order_by('-updated_at')[:15]
    return render(request, 'neuro/catalog.html', {
        'user_chats': user_chats,
        'current_chat_id': None,
    })


@login_required
def files_page(request):
    """Страница «Мои файлы»"""
    user_chats = Chat.objects.filter(user=request.user).select_related('network').prefetch_related('messages').order_by(
        '-updated_at')[:15]
    return render(request, 'neuro/files.html', {
        'user_chats': user_chats,
        'current_chat_id': None,
    })


@login_required
def user_files_api(request):
    """API для получения списка файлов пользователя с пагинацией и фильтрацией по категории"""
    try:
        page = int(request.GET.get('page', 1))
        per_page = int(request.GET.get('per_page', 12))
        category = request.GET.get('category', 'all')

        files_queryset = GeneratedImage.objects.filter(message__chat__user=request.user).order_by('-created_at')

        # Фильтрация по категории
        if category == 'images':
            files_queryset = files_queryset.filter(media_type='image')
        elif category == 'videos':
            files_queryset = files_queryset.filter(media_type='video')
        # 'all' — без фильтрации

        paginator = Paginator(files_queryset, per_page)

        if page > paginator.num_pages:
            return JsonResponse({
                'success': True,
                'files': [],
                'has_next': False,
                'total': paginator.count,
                'current_page': page,
                'total_pages': paginator.num_pages
            })

        page_obj = paginator.page(page)

        result = []
        for f in page_obj:
            file_name = f.image.name
            ext = file_name.split('.')[-1].lower() if '.' in file_name else ''
            category_out = 'videos' if f.media_type == 'video' else 'images'
            size_bytes = f.image.size if f.image else 0
            size_mb = round(size_bytes / (1024 * 1024), 1)
            size_str = f"{size_mb} MB" if size_mb < 1000 else f"{round(size_mb / 1024, 1)} GB"

            result.append({
                'id': str(f.id),
                'name': f.prompt[:50] if f.prompt else f"File {f.id}",
                'ext': ext,
                'size': size_str,
                'date': f.created_at.strftime('%Y-%m-%d'),
                'category': category_out,
                'url': f.image.url,
                'type': ext,
                'media_type': f.media_type,
            })

        return JsonResponse({
            'success': True,
            'files': result,
            'has_next': page < paginator.num_pages,
            'current_page': page,
            'total_pages': paginator.num_pages,
            'total': paginator.count
        })
    except Exception as e:
        logger.error(f"Ошибка получения файлов: {e}")
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@csrf_exempt
@require_POST
def delete_file(request, file_id):
    """Удаление сгенерированного файла (изображения/видео)"""
    try:
        from .models import GeneratedImage
        file_obj = get_object_or_404(GeneratedImage, id=file_id, message__chat__user=request.user)
        # Удаляем физический файл из хранилища
        if file_obj.image and default_storage.exists(file_obj.image.name):
            default_storage.delete(file_obj.image.name)
        file_obj.delete()
        return JsonResponse({'success': True, 'message': 'Файл удалён'})
    except Exception as e:
        logger.error(f"Ошибка удаления файла {file_id}: {e}")
        return JsonResponse({'success': False, 'message': str(e)})

@login_required
@csrf_exempt
@require_POST
def save_chat_settings(request, chat_id):
    """API: сохранить настройки чата"""
    try:
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)
        data = json.loads(request.body)
        settings = data.get('settings', {})
        chat.settings = settings
        chat.save(update_fields=['settings'])
        return JsonResponse({'success': True})
    except Exception as e:
        logger.error(f"Ошибка сохранения настроек чата {chat_id}: {e}")
        return JsonResponse({'success': False, 'message': str(e)})


@login_required
def get_network_config_api(request, slug):
    """API для получения конфигурации и возможностей нейросети по slug"""
    try:
        network = get_object_or_404(NeuralNetwork, slug=slug, is_active=True)

        file_capabilities = {
            'archive': network.handle_archive,
            'text_files': network.handle_text_files,
            'photo': network.handle_photo,
            'video': network.handle_video,
        }

        config_json = None
        if network.provider == 'fal-ai' and network.config_json:
            config_json = network.config_json

        return JsonResponse({
            'success': True,
            'file_capabilities': file_capabilities,
            'config_json': config_json,
            'has_prompt': network.has_prompt,
            'prompt': network.prompt,
            'provider': network.provider,
            'model_name': network.model_name,
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)})
