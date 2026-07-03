from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, IsAuthenticatedOrReadOnly
from rest_framework.response import Response
from rest_framework import serializers, status
from django.shortcuts import get_object_or_404
from django.utils.text import slugify
import uuid

from aitext.models import Persona
from api.authentication import CsrfExemptSessionAuthentication


class PersonaSerializer(serializers.ModelSerializer):
    is_own = serializers.SerializerMethodField()
    network_name = serializers.SerializerMethodField()
    chat_network_slug = serializers.SerializerMethodField()

    class Meta:
        model = Persona
        fields = [
            'id', 'name', 'slug', 'description', 'system_prompt',
            'avatar_url', 'network', 'network_name', 'chat_network_slug',
            'is_public', 'is_active', 'order', 'is_own', 'created_at',
        ]
        read_only_fields = ['id', 'slug', 'is_own', 'created_at']

    def get_is_own(self, obj):
        request = self.context.get('request')
        return request and request.user.is_authenticated and obj.user_id == request.user.id

    def get_network_name(self, obj):
        return obj.network.name if obj.network else None

    def get_chat_network_slug(self, obj):
        """Слаг модели для старта чата: своя модель персоны либо дефолтная текстовая."""
        net = obj.network
        if net and net.is_active:
            return net.slug
        if not hasattr(self, '_default_slug'):
            from aitext.models import NeuralNetwork
            default = (
                NeuralNetwork.objects
                .filter(is_active=True, provider='openrouter')
                .order_by('id')
                .first()
            )
            self._default_slug = default.slug if default else None
        return self._default_slug


class PersonaListCreateView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticatedOrReadOnly]

    def get(self, request):
        qs = Persona.objects.filter(is_public=True, is_active=True)
        if request.user.is_authenticated:
            own = Persona.objects.filter(user=request.user, is_active=True)
            from django.db.models import Q
            qs = Persona.objects.filter(
                Q(is_public=True, is_active=True) | Q(user=request.user, is_active=True)
            ).distinct()
        return Response(PersonaSerializer(qs, many=True, context={'request': request}).data)

    def post(self, request):
        if not request.user.is_authenticated:
            return Response({'detail': 'Authentication required'}, status=status.HTTP_401_UNAUTHORIZED)

        name = (request.data.get('name') or '').strip()
        if not name:
            return Response({'detail': 'name is required'}, status=status.HTTP_400_BAD_REQUEST)

        system_prompt = (request.data.get('system_prompt') or '').strip()
        if not system_prompt:
            return Response({'detail': 'system_prompt is required'}, status=status.HTTP_400_BAD_REQUEST)

        base_slug = slugify(name, allow_unicode=False) or 'persona'
        slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"

        persona = Persona.objects.create(
            name=name,
            slug=slug,
            description=(request.data.get('description') or '').strip(),
            system_prompt=system_prompt,
            avatar_url=(request.data.get('avatar_url') or '').strip(),
            user=request.user,
            is_public=False,
        )
        return Response(PersonaSerializer(persona, context={'request': request}).data, status=status.HTTP_201_CREATED)


class PersonaDetailView(APIView):
    authentication_classes = [CsrfExemptSessionAuthentication]
    permission_classes = [IsAuthenticated]

    def delete(self, request, persona_id):
        persona = get_object_or_404(Persona, id=persona_id, user=request.user)
        persona.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, persona_id):
        persona = get_object_or_404(Persona, id=persona_id, user=request.user)
        allowed = ['name', 'description', 'system_prompt', 'avatar_url']
        for field in allowed:
            if field in request.data:
                setattr(persona, field, request.data[field])
        persona.save()
        return Response(PersonaSerializer(persona, context={'request': request}).data)
