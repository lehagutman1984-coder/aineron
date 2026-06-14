from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from users.models import LegalDocument


class LegalPrivacyView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        doc = LegalDocument.get_privacy()
        return Response({
            'title': doc.title,
            'content': doc.content,
            'last_updated': doc.last_updated.isoformat(),
        })


class LegalTermsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        doc = LegalDocument.get_terms()
        return Response({
            'title': doc.title,
            'content': doc.content,
            'last_updated': doc.last_updated.isoformat(),
        })
