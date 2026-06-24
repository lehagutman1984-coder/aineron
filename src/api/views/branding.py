from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny


class BrandingView(APIView):
    """GET /v1/branding/?host=<hostname> — used by Next.js middleware."""
    permission_classes = [AllowAny]

    def get(self, request):
        host = request.query_params.get('host', '')
        if not host:
            return Response({'branding': None})

        from teams.middleware import OrganizationBrandingMiddleware
        m = OrganizationBrandingMiddleware(None)
        b = m._lookup(host.lower())

        if not b:
            return Response({'branding': None})

        return Response({
            'branding': {
                'subdomain': b.subdomain,
                'custom_domain': b.custom_domain,
                'logo_url': b.logo_url,
                'primary_color': b.primary_color,
                'company_name': b.company_name or b.organization.name,
                'support_email': b.support_email,
                'org_id': b.organization_id,
            }
        })
