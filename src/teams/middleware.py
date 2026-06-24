from django.core.cache import cache


class OrganizationBrandingMiddleware:
    """Resolves subdomain/custom_domain → OrganizationBranding and attaches to request."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.org_branding = self._resolve(request)
        return self.get_response(request)

    def _resolve(self, request):
        host = request.get_host().split(':')[0].lower()
        cache_key = f'org_branding:{host}'
        cached = cache.get(cache_key)
        if cached is not None:
            return cached if cached != '__none__' else None

        branding = self._lookup(host)
        cache.set(cache_key, branding if branding else '__none__', timeout=300)
        return branding

    def _lookup(self, host):
        from teams.models import OrganizationBranding
        try:
            # Check custom domain first
            b = OrganizationBranding.objects.select_related('organization').get(
                custom_domain=host, is_active=True
            )
            return b
        except OrganizationBranding.DoesNotExist:
            pass

        # Check subdomain (e.g. "acme" from "acme.aineron.ru")
        parts = host.split('.')
        if len(parts) >= 3:
            subdomain = parts[0]
            try:
                b = OrganizationBranding.objects.select_related('organization').get(
                    subdomain=subdomain, is_active=True
                )
                return b
            except OrganizationBranding.DoesNotExist:
                pass
        return None
