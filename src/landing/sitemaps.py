# landing/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse

class StaticViewSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return ['index', 'privacy_policy', 'terms_of_service', 'api_docs', 'ide_integrations']

    def location(self, item):
        if item == 'index':
            return reverse('landing:index')
        elif item == 'privacy_policy':
            return '/privacy-policy/'
        elif item == 'terms_of_service':
            return '/terms/'
        elif item == 'api_docs':
            return reverse('landing:api_docs')
        elif item == 'ide_integrations':
            return reverse('landing:ide_integrations')