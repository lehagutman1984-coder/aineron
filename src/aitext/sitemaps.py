# aitext/sitemaps.py
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from .models import NeuralNetwork


class NeuralNetworkSitemap(Sitemap):
    changefreq = 'weekly'
    priority = 0.9

    def items(self):
        return NeuralNetwork.objects.filter(is_active=True).order_by('order', 'name')

    def location(self, obj):
        return reverse('aitext:chat_landing', args=[obj.slug])

    def lastmod(self, obj):
        return None
