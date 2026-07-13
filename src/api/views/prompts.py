from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework import serializers, status
from django.shortcuts import get_object_or_404

from api.i18n import resolve_catalog_lang, translated_field
from aitext.models import PromptTemplate


class PromptTemplateSerializer(serializers.ModelSerializer):
    is_own = serializers.SerializerMethodField()

    class Meta:
        model = PromptTemplate
        fields = ['id', 'title', 'content', 'category', 'icon', 'is_public', 'is_own', 'created_at']
        read_only_fields = ['id', 'is_own', 'created_at']

    def get_is_own(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.user_id == request.user.id

    def to_representation(self, instance):
        # title/content остаются обычными полями для записи (POST/PATCH пишут
        # «сырое» поле как раньше) — перевод подставляется только на чтение,
        # и только когда явно запрошен ?lang= (см. api/i18n.py).
        data = super().to_representation(instance)
        lang = self.context.get('lang')
        if lang:
            data['title'] = translated_field(instance, 'title', lang)
            data['content'] = translated_field(instance, 'content', lang)
        return data


class PromptListCreateView(APIView):
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        # Built-in (user=None) + user's own prompts
        qs = PromptTemplate.objects.filter(user__isnull=True, is_public=True)
        if request.user.is_authenticated:
            user_qs = PromptTemplate.objects.filter(user=request.user)
            from django.db.models import QuerySet
            qs = (qs | user_qs).order_by('order', 'created_at')

        category = request.query_params.get('category')
        if category:
            qs = qs.filter(category=category)

        context = {'request': request, 'lang': resolve_catalog_lang(request)}
        return Response(PromptTemplateSerializer(qs, many=True, context=context).data)

    def post(self, request):
        serializer = PromptTemplateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save(user=request.user, is_public=False)
        return Response(serializer.data, status=201)


class PromptDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_own(self, request, pk):
        return get_object_or_404(PromptTemplate, pk=pk, user=request.user)

    def patch(self, request, pk):
        prompt = self._get_own(request, pk)
        serializer = PromptTemplateSerializer(
            prompt, data=request.data, partial=True, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request, pk):
        self._get_own(request, pk).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
