"""
2026-10-01 (аудит безопасности, API_SECURITY_AUDIT_2026-10-01.md, пункт 5/16):
регрессионные тесты — ASR отклоняет файлы крупнее реального лимита Whisper и
неизвестные модели; TTS отклоняет модели вне белого списка.

Запуск: python manage.py test api.tests_audio_limits
"""
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APITestCase
from rest_framework import status

User = get_user_model()


def _user(email='audio@test.ru'):
    u = User.objects.create_user(username=email, email=email, password='x')
    u.email_verified = True
    u.save(update_fields=['email_verified'])
    u.set_kopecks(100000)
    return u


class AudioLimitsTests(APITestCase):
    def setUp(self):
        self.user = _user()
        self.client.force_authenticate(user=self.user)

    def test_oversized_asr_file_rejected(self):
        big = SimpleUploadedFile('big.mp3', b'0' * (26 * 1024 * 1024), content_type='audio/mpeg')
        resp = self.client.post('/api/v1/audio/transcriptions', {'file': big}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['error']['code'], 'file_too_large')
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100000)  # ничего не списано

    def test_unknown_asr_model_rejected(self):
        small = SimpleUploadedFile('small.mp3', b'0' * 1024, content_type='audio/mpeg')
        resp = self.client.post('/api/v1/audio/transcriptions', {'file': small, 'model': 'some-expensive-model'}, format='multipart')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['error']['code'], 'model_not_found')

    def test_unknown_tts_model_rejected(self):
        resp = self.client.post('/api/v1/audio/speech', {'input': 'hello', 'model': 'some-expensive-tts'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(resp.data['error']['code'], 'model_not_found')
        self.user.refresh_from_db()
        self.assertEqual(self.user.balance_kopecks, 100000)

    def test_broken_tts1_model_rejected(self):
        # tts-1 реально сломан на апимарте — убран из allowlist, а не только
        # из DEFAULT_TTS_MODEL (клиент мог явно запросить его раньше).
        resp = self.client.post('/api/v1/audio/speech', {'input': 'hello', 'model': 'tts-1'}, format='json')
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)
