from rest_framework import serializers
from aitext.models import Category, NeuralNetwork, FAQ
from api.i18n import translated_field


class FAQSerializer(serializers.ModelSerializer):
    question = serializers.SerializerMethodField()
    answer = serializers.SerializerMethodField()

    class Meta:
        model = FAQ
        fields = ['id', 'question', 'answer', 'order']

    def get_question(self, obj):
        return translated_field(obj, 'question', self.context.get('lang'))

    def get_answer(self, obj):
        return translated_field(obj, 'answer', self.context.get('lang'))


class CategorySerializer(serializers.ModelSerializer):
    name = serializers.SerializerMethodField()

    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'icon', 'order']

    def get_name(self, obj):
        return translated_field(obj, 'name', self.context.get('lang'))


class NeuralNetworkListSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()
    output_type = serializers.SerializerMethodField()
    description = serializers.SerializerMethodField()
    seo_title = serializers.SerializerMethodField()
    seo_description = serializers.SerializerMethodField()
    i2v = serializers.SerializerMethodField()

    class Meta:
        model = NeuralNetwork
        fields = [
            'id', 'name', 'slug', 'category', 'avatar',
            'description', 'cost_per_message', 'cost_kopecks', 'provider',
            'is_popular', 'is_free', 'unlimited', 'messages_limit',
            'handle_photo', 'handle_video', 'handle_archive', 'handle_text_files',
            'seo_title', 'seo_description', 'model_name', 'order', 'output_type', 'i2v',
        ]

    def get_category(self, obj):
        if not obj.category:
            return None
        return CategorySerializer(obj.category, context=self.context).data

    def get_avatar(self, obj):
        return obj.get_avatar()

    def get_description(self, obj):
        return translated_field(obj, 'description', self.context.get('lang'))

    def get_seo_title(self, obj):
        return translated_field(obj, 'seo_title', self.context.get('lang'))

    def get_seo_description(self, obj):
        return translated_field(obj, 'seo_description', self.context.get('lang'))

    def get_output_type(self, obj):
        """'video' | 'image' | None — из config_json.metadata.output_type.

        Используется фронтом для каталога img2video-моделей ("Оживить").
        """
        try:
            return (obj.config_json or {}).get('metadata', {}).get('output_type')
        except Exception:
            return None

    def get_i2v(self, obj):
        """Мультиреференс image-to-video (B14): {max_images, mode} | None.

        mode: 'reference' — до max_images независимых референсных фото;
        'first_last' — ровно 2 фото трактуются как первый и последний кадр.
        None — модель не поддерживает image-to-video вовсе, либо поддерживает
        только одно фото (старое поведение, max_images не проставлен).
        """
        try:
            meta = (obj.config_json or {}).get('metadata', {})
            if not meta.get('supports_image_to_video'):
                return None
            max_images = meta.get('i2v_max_images')
            if not max_images or max_images < 2:
                return None
            return {'max_images': max_images, 'mode': meta.get('i2v_mode') or 'reference'}
        except Exception:
            return None


class NeuralNetworkDetailSerializer(NeuralNetworkListSerializer):
    faqs = serializers.SerializerMethodField()
    seo_keywords = serializers.SerializerMethodField()

    class Meta(NeuralNetworkListSerializer.Meta):
        fields = NeuralNetworkListSerializer.Meta.fields + [
            'seo_keywords', 'config_json', 'has_prompt',
            'is_direct', 'is_custom', 'max_tokens', 'faqs',
        ]

    def get_seo_keywords(self, obj):
        return translated_field(obj, 'seo_keywords', self.context.get('lang'))

    def get_faqs(self, obj):
        from django.db.models import Q
        faqs = FAQ.objects.filter(
            Q(show_everywhere=True) | Q(neural_network=obj)
        ).distinct().order_by('order')
        return FAQSerializer(faqs, many=True, context=self.context).data
