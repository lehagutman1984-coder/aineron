from rest_framework import serializers
from blog.models import Category, Post


class BlogCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'description', 'seo_title', 'seo_description', 'seo_keywords']


class BlogPostListSerializer(serializers.ModelSerializer):
    category = BlogCategorySerializer(read_only=True)
    preview_image_url = serializers.SerializerMethodField()
    author_name = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            'id', 'title', 'slug', 'category', 'preview_image_url',
            'preview_text', 'author_name', 'published_at',
            'views_count', 'show_on_main',
            'seo_title', 'seo_description', 'seo_keywords',
        ]

    def get_preview_image_url(self, obj):
        if not obj.preview_image:
            return None
        request = self.context.get('request')
        if request:
            return request.build_absolute_uri(obj.preview_image.url)
        return obj.preview_image.url

    def get_author_name(self, obj):
        if obj.author:
            return obj.author.get_full_name() or obj.author.username
        return None


class BlogPostDetailSerializer(BlogPostListSerializer):
    network_slugs = serializers.SerializerMethodField()

    class Meta(BlogPostListSerializer.Meta):
        fields = BlogPostListSerializer.Meta.fields + ['content', 'updated_at', 'network_slugs']

    def get_network_slugs(self, obj):
        return list(obj.neural_networks.values_list('slug', flat=True))
