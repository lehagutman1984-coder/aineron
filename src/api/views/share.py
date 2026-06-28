"""Sprint 7 — публичная галерея и шеринг сгенерированных медиа.

- GET  /v1/gallery/                       — публичная лента (все пользователи), без авторизации
- GET  /v1/generations/<slug>/public/     — публичный просмотр одной генерации по slug
- POST /v1/generations/<int:pk>/share/    — сделать публичной + выдать slug (владелец)
- POST /v1/generations/<int:pk>/unshare/  — сделать приватной (владелец)
"""
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework import status

from api.authentication import CsrfExemptSessionAuthentication
from aitext.models import GeneratedImage


def _anon_username(gen):
    """Аноним: никогда не раскрываем email/username целиком.

    API-генерации (message=null) не имеют владельца — отдаём 'API'.
    """
    user = None
    if gen.message_id and gen.message and gen.message.chat_id:
        user = gen.message.chat.user
    if user is None:
        return 'API'
    raw = (getattr(user, 'username', '') or getattr(user, 'email', '') or '').strip()
    if not raw:
        return 'Аноним'
    head = raw.split('@')[0]
    if len(head) <= 1:
        return head + '***'
    return head[0] + '***'


def _serialize_gallery_item(gen, request):
    image_url = ''
    try:
        if gen.image:
            image_url = request.build_absolute_uri(gen.image.url)
    except Exception:
        image_url = ''
    prompt = gen.prompt or ''
    return {
        'id': gen.id,
        'share_slug': gen.share_slug,
        'prompt': prompt[:100],
        'model_name': gen.model_name or '',
        'media_type': gen.media_type,
        'image_url': image_url,
        'created_at': gen.created_at.isoformat(),
        'username': _anon_username(gen),
    }


class GalleryView(APIView):
    """GET /v1/gallery/ — публичная лента всех публичных генераций."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request):
        page = int(request.query_params.get('page', 1) or 1)
        per_page = int(request.query_params.get('per_page', 24) or 24)
        per_page = max(1, min(per_page, 60))
        media_type = request.query_params.get('media_type', '')
        model_name = request.query_params.get('model_name', '')

        qs = (
            GeneratedImage.objects
            .filter(is_public=True)
            .exclude(image='')
            .select_related('message__chat__user')
            .order_by('-created_at')
        )
        if media_type in ('image', 'video'):
            qs = qs.filter(media_type=media_type)
        if model_name:
            qs = qs.filter(model_name=model_name)

        paginator = Paginator(qs, per_page)
        total = paginator.count
        total_pages = paginator.num_pages

        items = []
        if total > 0 and page <= total_pages:
            for gen in paginator.page(page):
                items.append(_serialize_gallery_item(gen, request))

        return Response({
            'items': items,
            'has_next': page < total_pages,
            'page': page,
            'total_pages': total_pages,
            'total': total,
        })


class PublicGenerationView(APIView):
    """GET /v1/generations/<slug>/public/ — публичный просмотр одной генерации."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [AllowAny]

    def get(self, request, slug):
        gen = (
            GeneratedImage.objects
            .filter(share_slug=slug, is_public=True)
            .select_related('message__chat__user')
            .first()
        )
        if gen is None or not gen.image:
            return Response(
                {'error': {'message': 'Генерация не найдена или не является публичной',
                           'type': 'not_found', 'code': 'not_found'}},
                status=status.HTTP_404_NOT_FOUND,
            )
        try:
            image_url = request.build_absolute_uri(gen.image.url)
        except Exception:
            image_url = ''
        return Response({
            'id': gen.id,
            'share_slug': gen.share_slug,
            'prompt': gen.prompt or '',
            'model_name': gen.model_name or '',
            'media_type': gen.media_type,
            'image_url': image_url,
            'width': gen.width,
            'height': gen.height,
            'seed': gen.seed,
            'created_at': gen.created_at.isoformat(),
            'username': _anon_username(gen),
        })


class GenerationShareView(APIView):
    """POST /v1/generations/<int:pk>/share/ — публикует генерацию владельца."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        gen = get_object_or_404(
            GeneratedImage, id=pk, message__chat__user=request.user
        )
        if not gen.image:
            return Response(
                {'error': {'message': 'Нельзя опубликовать незавершённую генерацию',
                           'type': 'invalid_request_error', 'code': None}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        gen.is_public = True
        gen.save(update_fields=['is_public'])
        if not gen.share_slug:
            gen.generate_share_slug()
        return Response({
            'id': gen.id,
            'is_public': True,
            'share_slug': gen.share_slug,
            'share_url': f'https://aineron.ru/g/{gen.share_slug}',
        })


class GenerationUnshareView(APIView):
    """POST /v1/generations/<int:pk>/unshare/ — снимает публикацию."""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        gen = get_object_or_404(
            GeneratedImage, id=pk, message__chat__user=request.user
        )
        gen.is_public = False
        gen.save(update_fields=['is_public'])
        return Response({
            'id': gen.id,
            'is_public': False,
            'share_slug': gen.share_slug,
        })
