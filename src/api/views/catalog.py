from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from aitext.models import Category, NeuralNetwork
from api.serializers.catalog import (
    CategorySerializer,
    NeuralNetworkListSerializer,
    NeuralNetworkDetailSerializer,
)


class CategoryListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = CategorySerializer
    queryset = Category.objects.all().order_by('order', 'name')


class NetworkListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = NeuralNetworkListSerializer

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
