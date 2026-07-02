from rest_framework import serializers
from aitext.models import Category, NeuralNetwork, FAQ


class FAQSerializer(serializers.ModelSerializer):
    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer', 'order']


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'order']


class NeuralNetworkListSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    avatar = serializers.SerializerMethodField()
    output_type = serializers.SerializerMethodField()

    class Meta:
        model = NeuralNetwork
        fields = [
            'id', 'name', 'slug', 'category', 'avatar',
            'description', 'cost_per_message', 'cost_kopecks', 'provider',
            'is_popular', 'unlimited', 'messages_limit',
            'handle_photo', 'handle_video', 'handle_archive', 'handle_text_files',
            'seo_title', 'seo_description', 'model_name', 'order', 'output_type',
        ]

    def get_avatar(self, obj):
        return obj.get_avatar()

    def get_output_type(self, obj):
        """'video' | 'image' | None — из config_json.metadata.output_type.

        Используется фронтом для каталога img2video-моделей ("Оживить").
        """
        try:
            return (obj.config_json or {}).get('metadata', {}).get('output_type')
        except Exception:
            return None


class NeuralNetworkDetailSerializer(NeuralNetworkListSerializer):
    faqs = serializers.SerializerMethodField()

    class Meta(NeuralNetworkListSerializer.Meta):
        fields = NeuralNetworkListSerializer.Meta.fields + [
            'seo_keywords', 'config_json', 'has_prompt',
            'is_direct', 'is_custom', 'max_tokens', 'faqs',
        ]

    def get_faqs(self, obj):
        from django.db.models import Q
        faqs = FAQ.objects.filter(
            Q(show_everywhere=True) | Q(neural_network=obj)
        ).distinct().order_by('order')
        return FAQSerializer(faqs, many=True).data
