from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from api.i18n import resolve_catalog_lang, translated_field
from users.models import LegalDocument


class LegalPrivacyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        doc = LegalDocument.get_privacy()
        lang = resolve_catalog_lang(request)
        return Response({
            'title': translated_field(doc, 'title', lang),
            'content': translated_field(doc, 'content', lang),
            'last_updated': doc.last_updated.isoformat(),
        })


class LegalTermsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        doc = LegalDocument.get_terms()
        lang = resolve_catalog_lang(request)
        return Response({
            'title': translated_field(doc, 'title', lang),
            'content': translated_field(doc, 'content', lang),
            'last_updated': doc.last_updated.isoformat(),
        })
