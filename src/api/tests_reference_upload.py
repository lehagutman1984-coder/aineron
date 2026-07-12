"""
Тест эндпоинта загрузки референсного фото до создания чата
(ChatStartForm — img2img со стартового экрана модели, см. img2img-баг 2026-07-12).
"""
import io

from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APITestCase

from aitext.models import FileAttachment

User = get_user_model()

_LOCMEM_CACHE = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}


def _png_bytes():
    from PIL import Image
    buf = io.BytesIO()
    Image.new('RGB', (32, 32), color='red').save(buf, format='PNG')
    buf.seek(0)
    return buf.read()


@override_settings(CACHES=_LOCMEM_CACHE)
class ReferenceImageUploadTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create(email='refupload@test.ru', username='refupload')

    def test_requires_auth(self):
        resp = self.client.post('/api/v1/uploads/reference-image/', {})
        self.assertEqual(resp.status_code, 401)

    def test_upload_without_chat_id(self):
        self.client.force_authenticate(self.user)
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('photo.png', _png_bytes(), content_type='image/png')
        resp = self.client.post('/api/v1/uploads/reference-image/', {'file': f}, format='multipart')
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertTrue(data['url'])
        self.assertEqual(data['media_type'], 'image')
        attachment = FileAttachment.objects.get(id=data['id'])
        self.assertIsNone(attachment.message_id)

    def test_rejects_non_image(self):
        self.client.force_authenticate(self.user)
        from django.core.files.uploadedfile import SimpleUploadedFile
        f = SimpleUploadedFile('doc.txt', b'hello', content_type='text/plain')
        resp = self.client.post('/api/v1/uploads/reference-image/', {'file': f}, format='multipart')
        self.assertEqual(resp.status_code, 400)
