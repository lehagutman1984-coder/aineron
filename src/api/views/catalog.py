from django.core.cache import cache
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from aitext.models import Category, NeuralNetwork
from api.i18n import resolve_catalog_lang
from api.serializers.catalog import (
    CategorySerializer,
    NeuralNetworkListSerializer,
    NeuralNetworkDetailSerializer,
)

# Каталог публичный и не зависит от пользователя — кэшируем целиком.
# Модели меняются только через админку, 60 сек устаревания не критичны.
_CATALOG_CACHE_TTL = 60


class CategoryListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    queryset = Category.objects.all().order_by('order', 'name')

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'lang': resolve_catalog_lang(self.request)}

    def list(self, request, *args, **kwargs):
        # Ключ учитывает ?lang= — иначе первый запрос "замораживает" язык
        # для всех остальных на _CATALOG_CACHE_TTL секунд.
        lang = resolve_catalog_lang(request)
        cache_key = f'catalog:categories:{lang or "default"}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, _CATALOG_CACHE_TTL)
        return response


class NetworkListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = NeuralNetworkListSerializer

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'lang': resolve_catalog_lang(self.request)}

    def list(self, request, *args, **kwargs):
        # Ключ учитывает все фильтры (category/provider/is_popular/is_free/lang)
        params = '&'.join(f'{k}={v}' for k, v in sorted(request.query_params.items()))
        cache_key = f'catalog:networks:{params}'
        cached = cache.get(cache_key)
        if cached is not None:
            return Response(cached)
        response = super().list(request, *args, **kwargs)
        cache.set(cache_key, response.data, _CATALOG_CACHE_TTL)
        return response

    def get_queryset(self):
        qs = NeuralNetwork.objects.filter(is_active=True).select_related('category')
        category = self.request.query_params.get('category')
        provider = self.request.query_params.get('provider')
        popular = self.request.query_params.get('is_popular')
        free = self.request.query_params.get('is_free')
        # Бесплатные модели живут в отдельной вкладке «Бесплатные»: по умолчанию
        # скрыты из общего каталога, показываются только при ?is_free=1.
        if free in ('1', 'true', 'True'):
            qs = qs.filter(is_free=True)
        else:
            qs = qs.filter(is_free=False)
        if category:
            qs = qs.filter(category__slug=category)
        if provider:
            qs = qs.filter(provider=provider)
        if popular in ('1', 'true', 'True'):
            qs = qs.filter(is_popular=True)
        return qs.order_by('order', 'name')


class NetworkDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = NeuralNetworkDetailSerializer
    queryset = NeuralNetwork.objects.filter(is_active=True).select_related('category')
    lookup_field = 'slug'

    def get_serializer_context(self):
        return {**super().get_serializer_context(), 'lang': resolve_catalog_lang(self.request)}
