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
    image_refs = serializers.SerializerMethodField()
    duration_options = serializers.SerializerMethodField()
    aspect_options = serializers.SerializerMethodField()

    class Meta:
        model = NeuralNetwork
        fields = [
            'id', 'name', 'slug', 'category', 'avatar',
            'description', 'cost_per_message', 'cost_kopecks', 'provider',
            'is_popular', 'is_free', 'unlimited', 'messages_limit',
            'handle_photo', 'handle_video', 'handle_archive', 'handle_text_files',
            'seo_title', 'seo_description', 'model_name', 'order', 'output_type', 'i2v',
            'image_refs', 'duration_options', 'aspect_options',
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

    def get_image_refs(self, obj):
        """Мультиреференс text-to-image (2026-09): {max_images} | None.

        В отличие от i2v (video), у изображений нет режима 'first_last' —
        все референсы равноправны. См. add_image_multi_reference.py — список
        моделей, где формат подтверждён живым вызовом провайдера, не все
        image-модели это умеют.
        """
        try:
            meta = (obj.config_json or {}).get('metadata', {})
            max_images = meta.get('image_max_reference_images')
            if not max_images or max_images < 2:
                return None
            return {'max_images': max_images}
        except Exception:
            return None

    def _find_field_options(self, obj, field_name):
        """Опции конкретного поля из config_json.ui_settings по имени.

        Раньше клиенты вроде AnimateImageModal.tsx хардкодили допустимые
        значения duration/aspect_ratio по названию модели ("isSora" и т.п.),
        что расходилось с реальными опциями конкретной модели в БД (напр.
        Sora допускает 4/8/12/16/20 сек, а хардкод предлагал 5/10/20 — запрос
        с невалидным значением гарантированно падал). Отдаём реальные опции,
        чтобы фронт строил контролы по факту, а не по догадке.
        """
        try:
            sections = (obj.config_json or {}).get('ui_settings', {}).get('sections', [])
            for section in sections:
                for field in section.get('fields', []):
                    if field.get('name') == field_name:
                        return [
                            {'value': o['value'], 'extra_cost': o.get('extra_cost', 0)}
                            for o in field.get('options', [])
                        ] or None
            return None
        except Exception:
            return None

    def get_duration_options(self, obj):
        return self._find_field_options(obj, 'duration')

    def get_aspect_options(self, obj):
        return self._find_field_options(obj, 'aspect_ratio')


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
