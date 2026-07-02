"""
POST /api/v1/audio/transcriptions — Whisper-совместимая транскрипция.
POST /api/v1/audio/speech — TTS (text-to-speech).
"""
import logging

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema

from aitext.tasks import get_laozhang_client

logger = logging.getLogger(__name__)

DEFAULT_TRANSCRIPTION_MODEL = 'whisper-1'
DEFAULT_TTS_MODEL = 'tts-1'
DEFAULT_TTS_VOICE = 'alloy'


class AudioTranscriptionsView(APIView):
    """POST /api/v1/audio/transcriptions"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(
        summary='Транскрипция аудио (Whisper-совместимый)',
        tags=['Audio'],
        description='Загрузите аудиофайл в поле `file`. Поддерживаемые форматы: mp3, mp4, wav, m4a, ogg.',
    )
    def post(self, request):
        audio_file = request.FILES.get('file')
        model_id = request.data.get('model', DEFAULT_TRANSCRIPTION_MODEL)
        language = request.data.get('language')
        prompt = request.data.get('prompt', '')
        response_format = request.data.get('response_format', 'json')
        temperature = float(request.data.get('temperature', 0))

        if not audio_file:
            return Response(
                {'error': {'message': "'file' is required", 'type': 'invalid_request_error', 'code': 'missing_file'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        ASR_COST_KOPECKS = 100  # 1 ₽ за транскрипцию
        if not user.has_enough_kopecks(ASR_COST_KOPECKS):
            from core.money import format_rub
            return Response(
                {'error': {'message': f'Insufficient balance: {format_rub(user.balance_kopecks)}.', 'type': 'insufficient_quota', 'code': 'insufficient_quota'}},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        client = get_laozhang_client()
        try:
            kwargs = {
                'model': model_id,
                'file': (audio_file.name, audio_file.read(), audio_file.content_type),
                'response_format': response_format,
                'temperature': temperature,
            }
            if language:
                kwargs['language'] = language
            if prompt:
                kwargs['prompt'] = prompt

            transcription = client.audio.transcriptions.create(**kwargs)
        except Exception as e:
            logger.error(f'[API] Ошибка транскрипции для {user.email}: {e}')
            return Response(
                {'error': {'message': str(e), 'type': 'api_error', 'code': 'upstream_error'}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Списываем фиксированную ставку (1 ₽) за транскрипцию
        import uuid as _uuid
        if not user.spend_kopecks(ASR_COST_KOPECKS, type='spend', reference=f'api-asr:{_uuid.uuid4().hex[:8]}'):
            logger.warning(f'[API] ASR: не удалось списать средства у {user.email} (баланс исчерпан гонкой)')

        if response_format == 'json':
            return Response({'text': getattr(transcription, 'text', str(transcription))})
        else:
            text = getattr(transcription, 'text', str(transcription))
            return HttpResponse(text, content_type='text/plain')


class AudioSpeechView(APIView):
    """POST /api/v1/audio/speech"""
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]

    @extend_schema(
        summary='Синтез речи (TTS, OpenAI-совместимый)',
        tags=['Audio'],
        description='Генерирует аудио из текста. Возвращает бинарный аудиофайл.',
    )
    def post(self, request):
        data = request.data
        model_id = data.get('model', DEFAULT_TTS_MODEL)
        text_input = data.get('input', '').strip()
        voice = data.get('voice', DEFAULT_TTS_VOICE)
        response_format = data.get('response_format', 'mp3')
        speed = float(data.get('speed', 1.0))

        if not text_input:
            return Response(
                {'error': {'message': "'input' is required", 'type': 'invalid_request_error', 'code': 'missing_input'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(text_input) > 4096:
            return Response(
                {'error': {'message': 'Input text exceeds 4096 characters', 'type': 'invalid_request_error', 'code': 'text_too_long'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        TTS_COST_KOPECKS = 100  # 1 ₽ за синтез
        if not user.has_enough_kopecks(TTS_COST_KOPECKS):
            from core.money import format_rub
            return Response(
                {'error': {'message': f'Insufficient balance: {format_rub(user.balance_kopecks)}.', 'type': 'insufficient_quota', 'code': 'insufficient_quota'}},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        client = get_laozhang_client()
        try:
            audio_response = client.audio.speech.create(
                model=model_id,
                voice=voice,
                input=text_input,
                response_format=response_format,
                speed=speed,
            )
        except Exception as e:
            logger.error(f'[API] Ошибка TTS для {user.email}: {e}')
            return Response(
                {'error': {'message': str(e), 'type': 'api_error', 'code': 'upstream_error'}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # Списываем фиксированную ставку (1 ₽) за TTS
        import uuid as _uuid
        if not user.spend_kopecks(TTS_COST_KOPECKS, type='spend', reference=f'api-tts:{_uuid.uuid4().hex[:8]}'):
            logger.warning(f'[API] TTS: не удалось списать средства у {user.email} (баланс исчерпан гонкой)')

        content_types = {
            'mp3': 'audio/mpeg', 'opus': 'audio/opus',
            'aac': 'audio/aac', 'flac': 'audio/flac', 'wav': 'audio/wav',
        }
        ct = content_types.get(response_format, 'audio/mpeg')
        audio_bytes = audio_response.content if hasattr(audio_response, 'content') else bytes(audio_response.read())
        return HttpResponse(audio_bytes, content_type=ct)
