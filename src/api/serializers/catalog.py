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

    class Meta:
        model = NeuralNetwork
        fields = [
            'id', 'name', 'slug', 'category', 'avatar',
            'description', 'cost_per_message', 'provider',
            'is_popular', 'unlimited', 'messages_limit',
            'handle_photo', 'handle_video', 'handle_archive', 'handle_text_files',
            'seo_title', 'seo_description', 'model_name', 'order',
        ]

    def get_avatar(self, obj):
        return obj.get_avatar()


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
