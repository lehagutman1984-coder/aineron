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
from api.error_messages import em


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
                    'message': em('files_rerun_no_source_chat'),
                    'type': 'invalid_request_error',
                    'code': None,
                }
            }, status=400)

        network = chat.network

        # Медиа-генерация доступна только на платных тарифах
        is_media = (
            (network.config_json or {}).get('metadata', {}).get('output_type') in ('image', 'video')
        ) or network.provider == 'fal-ai'
        if is_media and getattr(request.user.tariff, 'is_free', True):
            return Response({
                'error': {
                    'message': em('files_media_paid_only'),
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

        cost_kopecks = network.cost_kopecks
        if network.provider != 'fal-ai' and not request.user.has_enough_kopecks(cost_kopecks):
            from core.money import format_rub
            return Response({
                'error': {
                    'message': em('files_insufficient_funds', needed=format_rub(cost_kopecks), have=format_rub(request.user.balance_kopecks)),
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
                    'message': em('files_upscale_images_only'),
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
                    'message': em('files_upscale_paid_only'),
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

        network = gen.message.chat.network if gen.message_id else None
        cost_kopecks = network.cost_kopecks if network else 0
        if cost_kopecks and not request.user.has_enough_kopecks(cost_kopecks):
            from core.money import format_rub
            return Response({
                'error': {
                    'message': em('files_insufficient_funds', needed=format_rub(cost_kopecks), have=format_rub(request.user.balance_kopecks)),
                    'type': 'insufficient_quota',
                    'code': 'insufficient_quota',
                }
            }, status=402)

        image_url = request.build_absolute_uri(gen.image.url)

        # Создаём placeholder ДО запуска задачи — возвращаем его ID фронту для SSE-прогресса
        from aitext.fal_utils import UPSCALE_MODELS
        placeholder = GeneratedImage.objects.create(
            message=gen.message,
            user=request.user,
            image='',
            prompt=gen.prompt or '',
            media_type='image',
            model_name=UPSCALE_MODELS[0],
            provider='laozhang',
            source=gen.source or 'chat',
            parent_id=gen.id,
            params={'op': 'upscale', 'factor': factor, 'source_id': gen.id},
            status='running',
            progress=10,
        )

        from aitext.tasks import upscale_generation_task
        task = upscale_generation_task.delay(gen.id, request.user.id, factor, image_url, cost_kopecks, placeholder.id)

        return Response({
            'placeholder_id': placeholder.id,
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
                    'message': em('files_variations_no_source_chat'),
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
                    'message': em('files_variations_paid_only'),
                    'type': 'insufficient_permissions',
                    'code': 'requires_paid_plan',
                }
            }, status=402)

        cost_kopecks = network.cost_kopecks
        total_cost_kopecks = cost_kopecks * count
        if not request.user.has_enough_kopecks(total_cost_kopecks):
            from core.money import format_rub
            return Response({
                'error': {
                    'message': em('files_insufficient_funds_variations', needed=format_rub(total_cost_kopecks), count=count, have=format_rub(request.user.balance_kopecks)),
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


class GenerationDescribeView(APIView):
    """POST /v1/generations/<pk>/describe/

    Анализирует изображение через GPT-4o и возвращает детальный промпт.
    Возвращает { "prompt": "..." }
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from django.conf import settings as django_settings
        from openai import OpenAI
        import requests as _req

        gen = get_object_or_404(
            GeneratedImage, _user_gens_q(request.user), id=pk
        )

        # Получаем URL изображения
        if gen.image:
            # Строим абсолютный URL
            request_host = request.build_absolute_uri('/')[:-1]
            image_url = request_host + gen.image.url
        else:
            return Response({'error': {'message': em('files_image_not_found'), 'type': 'not_found', 'code': None}}, status=404)

        try:
            client = OpenAI(
                api_key=django_settings.LAOZHANG_API_KEY,
                base_url=django_settings.LAOZHANG_API_URL,
            )
            describe_prompt = (
                "Analyze this AI-generated image and write a detailed text-to-image prompt "
                "that would recreate it. Include: main subject, art style, lighting, colors, "
                "composition, mood, technical details (camera angle, depth of field). "
                "Write in English. Be specific and detailed. Max 200 words. "
                "Return only the prompt text, no explanations."
            )
            resp = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "image_url", "image_url": {"url": image_url}},
                            {"type": "text", "text": describe_prompt},
                        ],
                    }
                ],
                max_tokens=400,
            )
            prompt_text = resp.choices[0].message.content.strip() if resp.choices else ""
            if not prompt_text:
                return Response({'error': {'message': em('files_describe_failed'), 'type': 'api_error', 'code': None}}, status=500)
            return Response({'prompt': prompt_text})
        except Exception as e:
            return Response({'error': {'message': str(e), 'type': 'api_error', 'code': None}}, status=500)


class GenerationFavoriteToggleView(APIView):
    """POST /v1/generations/<pk>/favorite/ — добавить/убрать из избранного."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        gen = get_object_or_404(GeneratedImage, _user_gens_q(request.user), id=pk)
        gen.is_favorite = not gen.is_favorite
        gen.save(update_fields=['is_favorite'])
        return Response({'id': gen.id, 'is_favorite': gen.is_favorite})


class FavoritesListView(APIView):
    """GET /v1/favorites/ — список избранных генераций текущего пользователя."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = int(request.query_params.get('page', 1) or 1)
        per_page = int(request.query_params.get('per_page', 24) or 24)
        per_page = max(1, min(per_page, 60))
        media_type = request.query_params.get('media_type', '')

        qs = (
            GeneratedImage.objects
            .filter(_user_gens_q(request.user), is_favorite=True)
            .exclude(image='')
            .order_by('-created_at')
        )
        if media_type in ('image', 'video'):
            qs = qs.filter(media_type=media_type)

        from django.core.paginator import Paginator as _Pager
        pager = _Pager(qs, per_page)
        total = pager.count
        items = []
        if total > 0 and page <= pager.num_pages:
            for gen in pager.page(page):
                image_url = ''
                try:
                    if gen.image:
                        image_url = request.build_absolute_uri(gen.image.url)
                except Exception:
                    pass
                items.append({
                    'id': gen.id,
                    'image_url': image_url,
                    'prompt': (gen.prompt or '')[:120],
                    'model_name': gen.model_name or '',
                    'media_type': gen.media_type,
                    'is_favorite': True,
                    'created_at': gen.created_at.isoformat(),
                })
        return Response({
            'items': items,
            'has_next': page < pager.num_pages,
            'page': page,
            'total': total,
        })


class RemoveBackgroundView(APIView):
    """POST /v1/generations/<pk>/remove-background/ — удаление фона через rembg (локально).

    Возвращает {id, url} новой GeneratedImage с прозрачным PNG-фоном.
    Если rembg не установлен — 503 с понятным сообщением.
    """
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            from rembg import remove as rembg_remove
        except ImportError:
            return Response(
                {'error': em('files_rembg_unavailable')},
                status=503
            )

        gen = get_object_or_404(GeneratedImage, pk=pk)
        owns = (gen.user_id == request.user.pk) or (
            gen.message_id and gen.message and gen.message.chat.user_id == request.user.pk
        )
        if not owns:
            return Response({'error': em('files_access_denied')}, status=status.HTTP_403_FORBIDDEN)

        try:
            img_bytes = gen.image.read()
        except Exception as e:
            return Response({'error': em('files_read_image_failed', error=e)}, status=500)

        try:
            result_bytes = rembg_remove(img_bytes)
        except Exception as e:
            return Response({'error': em('files_remove_background_failed', error=e)}, status=500)

        try:
            import uuid as _uuid
            from django.core.files.base import ContentFile

            owner = gen.user or (gen.message.chat.user if gen.message_id and gen.message else None)
            new_gen = GeneratedImage(
                message=gen.message,
                user=owner,
                prompt=(gen.prompt or ''),
                media_type='image',
                model_name=gen.model_name or '',
                parent=gen,
                status='done',
                progress=100,
            )
            filename = f'nobg_{_uuid.uuid4().hex[:12]}.png'
            new_gen.image.save(filename, ContentFile(result_bytes), save=False)
            new_gen.save()

            image_url = ''
            try:
                image_url = request.build_absolute_uri(new_gen.image.url)
            except Exception:
                pass

            return Response({'id': new_gen.id, 'url': image_url})
        except Exception as e:
            return Response({'error': em('files_save_failed', error=e)}, status=500)
