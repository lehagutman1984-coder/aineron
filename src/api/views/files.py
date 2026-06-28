from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from api.authentication import CsrfExemptSessionAuthentication
from aitext.models import GeneratedImage, Message
from aitext.tasks import generate_ai_response


def _user_gens_q(user):
    """Q-фильтр для генераций пользователя: чат-генерации + API-генерации (message=null)."""
    return Q(message__chat__user=user) | Q(user=user)


class UserFilesView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 24))
        category = request.query_params.get('category', 'all')

        qs = GeneratedImage.objects.filter(
            _user_gens_q(request.user)
        ).exclude(image='').order_by('-created_at')

        if category == 'images':
            qs = qs.filter(media_type='image')
        elif category == 'videos':
            qs = qs.filter(media_type='video')

        paginator = Paginator(qs, per_page)
        total = paginator.count
        total_pages = paginator.num_pages

        if page > total_pages and total_pages > 0:
            return Response({
                'files': [],
                'has_next': False,
                'page': page,
                'total_pages': total_pages,
                'total': total,
            })

        files = []
        if total > 0:
            for f in paginator.page(min(page, total_pages)):
                size_bytes = 0
                try:
                    size_bytes = f.image.size if f.image else 0
                except Exception:
                    pass
                size_mb = size_bytes / (1024 * 1024)
                size_str = f"{size_mb:.1f} MB" if size_mb < 1000 else f"{size_mb / 1024:.1f} GB"

                file_name = f.image.name if f.image else ''
                ext = file_name.rsplit('.', 1)[-1].lower() if '.' in file_name else ''

                files.append({
                    'id': str(f.id),
                    'url': request.build_absolute_uri(f.image.url) if f.image else '',
                    'prompt': f.prompt[:80] if f.prompt else f'Файл {f.id}',
                    'media_type': f.media_type,
                    'ext': ext,
                    'size': size_str,
                    'width': f.width,
                    'height': f.height,
                    'params': f.params,
                    'seed': f.seed,
                    'model_name': f.model_name,
                    'provider': f.provider,
                    'parent_id': f.parent_id,
                    'source': f.source,
                    'is_public': f.is_public,
                    'share_slug': f.share_slug,
                    'created_at': f.created_at.isoformat(),
                })

        return Response({
            'files': files,
            'has_next': page < total_pages,
            'page': page,
            'total_pages': total_pages,
            'total': total,
        })


class UserFileDeleteView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, file_id):
        file_obj = get_object_or_404(
            GeneratedImage, _user_gens_q(request.user), id=file_id
        )
        if file_obj.image and default_storage.exists(file_obj.image.name):
            default_storage.delete(file_obj.image.name)
        file_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class GenerationRerunView(APIView):
    """Sprint 4: повторная генерация по тем же параметрам (тот же seed/настройки).

    POST /v1/generations/<pk>/rerun/
    Создаёт новую пару сообщений (user+assistant) в том же чате с настройками
    исходной генерации и запускает generate_ai_response. Списание звёзд для
    fal-ai выполняется внутри задачи (как и в обычном flow), поэтому здесь
    только проверки тарифа/баланса для понятной ошибки.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        gen = get_object_or_404(
            GeneratedImage, _user_gens_q(request.user), id=pk
        )
        chat = gen.message.chat if gen.message_id else None
        if chat is None:
            return Response({
                'error': {
                    'message': 'Эту генерацию нельзя повторить (нет исходного чата).',
                    'type': 'invalid_request_error',
                    'code': None,
                }
            }, status=400)

        network = chat.network

        # Медиа-генерация доступна только на платных тарифах
        is_media = network.handle_video or network.handle_photo or (
            (network.config_json or {}).get('metadata', {}).get('output_type') in ('image', 'video')
        ) or network.provider == 'fal-ai'
        if is_media and getattr(request.user.tariff, 'is_free', True):
            return Response({
                'error': {
                    'message': 'Генерация изображений и видео доступна только на платных тарифах.',
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

        cost = network.cost_per_message
        if network.provider != 'fal-ai' and request.user.pages_count < cost:
            return Response({
                'error': {
                    'message': f'Недостаточно звёзд. Нужно {cost} зв., у вас {request.user.pages_count} зв.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        # Восстанавливаем настройки исходной генерации. validate_and_merge_settings
        # игнорирует ключи вне ui_settings, поэтому служебные model/prompt/image
        # безопасны, но убираем их для чистоты. seed закрепляем явно.
        settings = dict(gen.params or {})
        for k in ('model', 'prompt', 'image'):
            settings.pop(k, None)
        if gen.seed is not None:
            settings['seed'] = gen.seed

        prompt = gen.prompt or ''

        user_message = Message.objects.create(
            chat=chat, role='user', content=prompt,
            status=Message.Status.COMPLETED, settings=settings,
        )
        assistant_message = Message.objects.create(
            chat=chat, role='assistant', content='', status=Message.Status.PENDING,
        )

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        generate_ai_response.delay(assistant_message.id)

        return Response({
            'chat_id': chat.id,
            'message_id': assistant_message.id,
            'generation_id': None,
        }, status=201)


class GenerationUpscaleView(APIView):
    """Sprint 6: апскейл изображения в 2x/4x через upscale-модель провайдера.

    POST /v1/generations/<pk>/upscale/
    Body: {"factor": 2}  # 2 или 4
    Запускает Celery-задачу (биллинг/возврат — внутри задачи) и возвращает task_id.
    Результат появится в галерее (/account/files/) по завершении.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        gen = get_object_or_404(
            GeneratedImage, _user_gens_q(request.user), id=pk
        )
        if gen.media_type != 'image' or not gen.image:
            return Response({
                'error': {
                    'message': 'Апскейл доступен только для изображений.',
                    'type': 'invalid_request_error',
                    'code': None,
                }
            }, status=400)

        try:
            factor = int(request.data.get('factor', 2))
        except (ValueError, TypeError):
            factor = 2
        if factor not in (2, 4):
            factor = 2

        # Медиа-обработка доступна только на платных тарифах
        if getattr(request.user.tariff, 'is_free', True):
            return Response({
                'error': {
                    'message': 'Апскейл изображений доступен только на платных тарифах.',
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

        network = gen.message.chat.network if gen.message_id else None
        cost = network.cost_per_message if network else 0
        if cost and request.user.pages_count < cost:
            return Response({
                'error': {
                    'message': f'Недостаточно звёзд. Нужно {cost} зв., у вас {request.user.pages_count} зв.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        image_url = request.build_absolute_uri(gen.image.url)

        from aitext.tasks import upscale_generation_task
        task = upscale_generation_task.delay(gen.id, request.user.id, factor, image_url, cost)

        return Response({
            'task_id': task.id,
            'status': 'pending',
            'factor': factor,
        }, status=202)


class GenerationVariationsView(APIView):
    """Sprint 6: создаёт N вариаций изображения (тот же промт/модель, разные сиды).

    POST /v1/generations/<pk>/variations/
    Body: {"count": 4}
    Создаёт N пар сообщений (user+assistant) с настройками исходной генерации,
    но БЕЗ закреплённого seed — провайдер выдаёт свежий seed на каждую вариацию.
    Возвращает {chat_id, message_ids}.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        gen = get_object_or_404(
            GeneratedImage, _user_gens_q(request.user), id=pk
        )
        chat = gen.message.chat if gen.message_id else None
        if chat is None:
            return Response({
                'error': {
                    'message': 'Для этой генерации нельзя создать вариации (нет исходного чата).',
                    'type': 'invalid_request_error',
                    'code': None,
                }
            }, status=400)

        try:
            count = int(request.data.get('count', 4))
        except (ValueError, TypeError):
            count = 4
        count = max(1, min(count, 4))

        network = chat.network

        if getattr(request.user.tariff, 'is_free', True):
            return Response({
                'error': {
                    'message': 'Создание вариаций доступно только на платных тарифах.',
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

        cost = network.cost_per_message
        total_cost = cost * count
        if request.user.pages_count < total_cost:
            return Response({
                'error': {
                    'message': f'Недостаточно звёзд. Нужно {total_cost} зв. на {count} вариаций, у вас {request.user.pages_count} зв.',
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        # Настройки исходной генерации без служебных ключей и БЕЗ seed (свежий seed на вариацию).
        # num_images=1 — чтобы count вариаций = count изображений (а не count×num_images).
        base_settings = dict(gen.params or {})
        for k in ('model', 'prompt', 'image', 'seed'):
            base_settings.pop(k, None)
        base_settings['num_images'] = 1

        prompt = gen.prompt or ''
        message_ids = []
        for _ in range(count):
            user_message = Message.objects.create(
                chat=chat, role='user', content=prompt,
                status=Message.Status.COMPLETED, settings=dict(base_settings),
            )
            assistant_message = Message.objects.create(
                chat=chat, role='assistant', content='', status=Message.Status.PENDING,
            )
            generate_ai_response.delay(assistant_message.id)
            message_ids.append(assistant_message.id)

        chat.updated_at = timezone.now()
        chat.save(update_fields=['updated_at'])

        return Response({
            'chat_id': chat.id,
            'message_ids': message_ids,
            'count': count,
        }, status=201)
