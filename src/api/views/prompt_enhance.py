"""Sprint 5 — AI Prompt Enhancer для генерации изображений.

POST /api/v1/images/enhance-prompt/
    Body: { "prompt": "...", "style": "photorealistic|anime|oil_painting|..." }
    Расширяет короткое описание пользователя в детальный англоязычный
    промпт для image-моделей через быструю текстовую модель (laozhang.ai).
    Returns: { "enhanced_prompt": "...", "original_prompt": "..." }
"""
import logging

from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from drf_spectacular.utils import extend_schema

from api.authentication import CsrfExemptSessionAuthentication

logger = logging.getLogger(__name__)

# Быстрая текстовая модель, проверенно резолвится на laozhang (см. translate_to_english).
ENHANCE_MODEL = "deepseek-v3"

# Человекочитаемые подсказки стиля → инструкция для модели.
STYLE_HINTS = {
    'photorealistic': 'photorealistic, ultra-detailed, sharp focus, natural lighting',
    'anime': 'anime style, vibrant colors, clean line art, cel shading',
    'oil_painting': 'oil painting, visible brush strokes, rich texture, classical composition',
    'watercolor': 'watercolor painting, soft gradients, delicate washes, paper texture',
    'digital_art': 'digital art, highly detailed, concept art, trending on artstation',
    'cinematic': 'cinematic lighting, dramatic shadows, film grain, wide aspect framing',
    '3d_render': '3d render, octane render, physically based materials, soft global illumination',
    'pixel_art': 'pixel art, 8-bit, crisp pixels, limited palette',
    'minimalist': 'minimalist, clean composition, negative space, flat design',
}

SYSTEM_PROMPT = (
    "You are a professional image prompt writer. Expand the user's brief description "
    "into a detailed, vivid image generation prompt in English. Include lighting, style, "
    "composition, details. Return only the enhanced prompt, nothing else."
)


class ImagePromptEnhanceView(APIView):
    """POST /api/v1/images/enhance-prompt/"""
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    @extend_schema(
        summary='AI-улучшение промпта для генерации изображений',
        tags=['Images'],
    )
    def post(self, request):
        prompt = (request.data.get('prompt') or '').strip()
        style = (request.data.get('style') or '').strip()

        if not prompt:
            return Response(
                {'error': {'message': "Поле 'prompt' обязательно", 'type': 'invalid_request_error', 'code': 'missing_prompt'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(prompt) > 2000:
            return Response(
                {'error': {'message': 'Слишком длинный промпт (макс. 2000 символов)', 'type': 'invalid_request_error', 'code': 'prompt_too_long'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user_content = prompt
        style_hint = STYLE_HINTS.get(style)
        if style_hint:
            user_content = f"{prompt}\n\nDesired style: {style} ({style_hint})."
        elif style:
            user_content = f"{prompt}\n\nDesired style: {style}."

        try:
            # Импорт здесь, чтобы избежать тяжёлой загрузки Celery-зависимостей на старте.
            from aitext.tasks import get_laozhang_client

            client = get_laozhang_client()
            completion = client.chat.completions.create(
                model=ENHANCE_MODEL,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.8,
                max_tokens=600,
            )
            enhanced = (completion.choices[0].message.content or '').strip()
            if not enhanced:
                raise ValueError('Пустой ответ от модели')
        except Exception as e:  # noqa: BLE001
            logger.error(f'[enhance-prompt] Ошибка улучшения промпта для {request.user.email}: {e}')
            return Response(
                {'error': {'message': 'Не удалось улучшить промпт. Попробуйте ещё раз.', 'type': 'api_error', 'code': 'enhance_failed'}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response({
            'enhanced_prompt': enhanced,
            'original_prompt': prompt,
        })
