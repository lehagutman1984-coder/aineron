import uuid
import logging
from pathlib import Path
from django.shortcuts import get_object_or_404
from django.core.files.storage import default_storage
from django.core.files.base import ContentFile
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser

from aitext.models import Chat, FileAttachment
from aitext.file_utils import guess_media_type, extract_text_from_file

logger = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = {
    '.jpg', '.jpeg', '.png', '.gif', '.webp',
    '.pdf',
    '.txt', '.md', '.csv', '.json',
    '.doc', '.docx', '.xls', '.xlsx',
    '.py', '.js', '.ts', '.jsx', '.tsx',
    '.html', '.css', '.xml', '.yaml', '.yml',
}

MAX_SIZE = 20 * 1024 * 1024  # 20 MB


class ChatFileUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, chat_id):
        chat = get_object_or_404(Chat, id=chat_id, user=request.user)

        file = request.FILES.get('file')
        if not file:
            return Response(
                {'error': {'message': 'Файл не передан', 'type': 'invalid_request_error', 'code': None}},
                status=400,
            )

        if file.size > MAX_SIZE:
            return Response(
                {'error': {'message': 'Файл слишком большой. Максимум 20 МБ', 'type': 'invalid_request_error', 'code': None}},
                status=400,
            )

        ext = Path(file.name).suffix.lower()
        if ext and ext not in ALLOWED_EXTENSIONS:
            return Response(
                {'error': {'message': f'Неподдерживаемый тип файла: {ext}', 'type': 'invalid_request_error', 'code': None}},
                status=400,
            )

        mime = file.content_type or 'application/octet-stream'
        storage_path = f"attachments/{request.user.id}/{chat_id}/{uuid.uuid4()}{ext}"

        file_bytes = file.read()
        saved_path = default_storage.save(storage_path, ContentFile(file_bytes))
        media_type = guess_media_type(mime, ext)

        attachment = FileAttachment.objects.create(
            message=None,
            filename=file.name,
            file_path=saved_path,
            file_size=len(file_bytes),
            mime_type=mime,
            media_type=media_type,
            source='uploaded',
        )

        # Extract text from documents and PDFs
        if media_type in ('other', 'pdf'):
            try:
                extracted = extract_text_from_file(None, file.name, file_bytes)
                if extracted:
                    attachment.extracted_text = extracted[:20000]
                    attachment.save(update_fields=['extracted_text'])
            except Exception as e:
                logger.warning(f"Text extraction failed for {file.name}: {e}")

        return Response({
            'id': str(attachment.id),
            'url': attachment.file_url,
            'filename': attachment.filename,
            'media_type': attachment.media_type,
            'mime_type': attachment.mime_type,
            'file_size': attachment.file_size,
        }, status=201)
