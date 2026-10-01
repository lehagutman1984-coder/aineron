"""
POST /api/v1/audio/transcriptions — Whisper-совместимая транскрипция.
POST /api/v1/audio/speech — TTS (text-to-speech).
"""
import logging
import uuid

from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from api.permissions import IsEmailVerified
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from drf_spectacular.utils import extend_schema

from aitext.providers import get_utility_client
from api.exceptions import InsufficientStarsError
from api.services.billing import flat_charge, flat_refund, insufficient_error_payload

logger = logging.getLogger(__name__)

DEFAULT_TRANSCRIPTION_MODEL = 'whisper-1'
# 2026-09-06: tts-1 реально сломан на apimart (400/500 в зависимости от
# payload, воспроизведено напрямую) — gpt-4o-mini-tts работает нормально на
# apimart и на cometapi, см. providers.py::get_utility_client.
DEFAULT_TTS_MODEL = 'gpt-4o-mini-tts'
DEFAULT_TTS_VOICE = 'alloy'

# 2026-09-06 (аудит безопасности, HIGH): цена ASR/TTS — плоские 100 коп. за
# вызов независимо от длины/модели (себестоимость переменная — апимарт
# биллит по минутам/символам). Два ограничения ниже НЕ решают вопрос цены
# по существу (это требует реального аудита тарифов апимарт на аудио,
# отдельная задача по методологии проекта — опт×маржа), но исключают худший
# сценарий: nginx пропускает файлы до 100 МБ (client_max_body_size), реальный
# Whisper принимает максимум ~25 МБ — без собственного ограничения разница
# уходила в апстрим и могла вернуть осмысленную ошибку ПОСЛЕ того, как мы
# уже приняли (и, если апстрим всё же проглотит файл, оплатим) низкобитрейтный
# файл на часы аудио за 1 ₽. Модель — белый список: raw model_id от клиента
# уходит прямо в provider.audio.*.create() без какой-либо проверки против
# своего каталога (в отличие от chat/images, тут нет NeuralNetwork вообще) —
# клиент мог выбрать более дорогую модель апимарт по той же плоской цене.
MAX_ASR_FILE_BYTES = 25 * 1024 * 1024  # реальный лимит Whisper, не наша прихоть
ALLOWED_ASR_MODELS = {'whisper-1'}
ALLOWED_TTS_MODELS = {'gpt-4o-mini-tts', 'tts-1-hd'}  # tts-1 сломан, см. выше


class AudioTranscriptionsView(APIView):
    """POST /api/v1/audio/transcriptions"""
    permission_classes = [IsAuthenticated, IsEmailVerified]
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
        if audio_file.size > MAX_ASR_FILE_BYTES:
            return Response(
                {'error': {'message': f'File exceeds {MAX_ASR_FILE_BYTES // (1024*1024)} MB limit', 'type': 'invalid_request_error', 'code': 'file_too_large'}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if model_id not in ALLOWED_ASR_MODELS:
            return Response(
                {'error': {'message': f"Unsupported model '{model_id}'", 'type': 'invalid_request_error', 'code': 'model_not_found'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        ASR_COST_KOPECKS = 100  # 1 ₽ за транскрипцию
        api_key = getattr(request, 'api_key', None)
        # Списываем ДО обращения к апстриму (раньше - после, и неудачное списание
        # лишь логировалось: апстрим уже выставил нам счёт). При ошибке - возврат.
        asr_ref = f'api-asr:{uuid.uuid4().hex[:16]}'
        try:
            org = flat_charge(user, api_key, ASR_COST_KOPECKS, asr_ref)
        except InsufficientStarsError as e:
            return Response(
                {'error': insufficient_error_payload(e)},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        client = get_utility_client()
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
            flat_refund(user, org, ASR_COST_KOPECKS, asr_ref)
            logger.error(f'[API] Ошибка транскрипции для {user.email}: {e}')
            return Response(
                {'error': {'message': str(e), 'type': 'api_error', 'code': 'upstream_error'}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        if response_format == 'json':
            return Response({'text': getattr(transcription, 'text', str(transcription))})
        else:
            text = getattr(transcription, 'text', str(transcription))
            return HttpResponse(text, content_type='text/plain')


class AudioSpeechView(APIView):
    """POST /api/v1/audio/speech"""
    permission_classes = [IsAuthenticated, IsEmailVerified]
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
        if model_id not in ALLOWED_TTS_MODELS:
            return Response(
                {'error': {'message': f"Unsupported model '{model_id}'", 'type': 'invalid_request_error', 'code': 'model_not_found'}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        user = request.user
        TTS_COST_KOPECKS = 100  # 1 ₽ за синтез
        api_key = getattr(request, 'api_key', None)
        tts_ref = f'api-tts:{uuid.uuid4().hex[:16]}'
        try:
            org = flat_charge(user, api_key, TTS_COST_KOPECKS, tts_ref)
        except InsufficientStarsError as e:
            return Response(
                {'error': insufficient_error_payload(e)},
                status=status.HTTP_402_PAYMENT_REQUIRED,
            )

        client = get_utility_client()
        try:
            audio_response = client.audio.speech.create(
                model=model_id,
                voice=voice,
                input=text_input,
                response_format=response_format,
                speed=speed,
            )
        except Exception as e:
            flat_refund(user, org, TTS_COST_KOPECKS, tts_ref)
            logger.error(f'[API] Ошибка TTS для {user.email}: {e}')
            return Response(
                {'error': {'message': str(e), 'type': 'api_error', 'code': 'upstream_error'}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        content_types = {
            'mp3': 'audio/mpeg', 'opus': 'audio/opus',
            'aac': 'audio/aac', 'flac': 'audio/flac', 'wav': 'audio/wav',
        }
        ct = content_types.get(response_format, 'audio/mpeg')
        audio_bytes = audio_response.content if hasattr(audio_response, 'content') else bytes(audio_response.read())
        return HttpResponse(audio_bytes, content_type=ct)
