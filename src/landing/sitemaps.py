from django.contrib.sitemaps import Sitemap


class StaticViewSitemap(Sitemap):
    changefreq = 'monthly'
    priority = 0.5

    def items(self):
        return ['index', 'privacy_policy', 'terms_of_service']

    def location(self, item):
        if item == 'index':
            return '/'
        elif item == 'privacy_policy':
            return '/privacy-policy/'
        elif item == 'terms_of_service':
            return '/terms/'
