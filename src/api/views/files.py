from django.core.files.storage import default_storage
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from api.authentication import CsrfExemptSessionAuthentication
from aitext.models import GeneratedImage


class UserFilesView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def get(self, request):
        page = int(request.query_params.get('page', 1))
        per_page = int(request.query_params.get('per_page', 24))
        category = request.query_params.get('category', 'all')

        qs = GeneratedImage.objects.filter(
            message__chat__user=request.user
        ).order_by('-created_at')

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
            GeneratedImage, id=file_id, message__chat__user=request.user
        )
        if file_obj.image and default_storage.exists(file_obj.image.name):
            default_storage.delete(file_obj.image.name)
        file_obj.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
