from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from blog.models import Category, Post
from api.serializers.blog import BlogCategorySerializer, BlogPostListSerializer, BlogPostDetailSerializer


class BlogCategoryListView(ListAPIView):
    queryset = Category.objects.all().order_by('name')
    serializer_class = BlogCategorySerializer
    permission_classes = [AllowAny]


class BlogPostListView(ListAPIView):
    serializer_class = BlogPostListSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        qs = Post.objects.filter(is_published=True).select_related('category', 'author')
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__slug=category)
        show_on_main = self.request.query_params.get('show_on_main')
        if show_on_main:
            qs = qs.filter(show_on_main=True)
        lang = (self.request.query_params.get('lang') or '').strip().lower()
        if lang in dict(Post.LANGUAGE_CHOICES):
            qs = qs.filter(language=lang)
        return qs.order_by('-published_at')


class BlogPostDetailView(RetrieveAPIView):
    queryset = Post.objects.filter(is_published=True).select_related('category', 'author').prefetch_related('neural_networks')
    serializer_class = BlogPostDetailSerializer
    permission_classes = [AllowAny]
    lookup_field = 'slug'

    def get_object(self):
        obj = super().get_object()
        Post.objects.filter(pk=obj.pk).update(views_count=obj.views_count + 1)
        return obj
