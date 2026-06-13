from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from aitext.models import Chat  # импорт модели чата
from .models import Post, Category


def blog_list(request):
    """Список статей"""
    # Получаем чаты пользователя для сайдбара
    user_chats = []
    current_chat_id = None
    if request.user.is_authenticated:
        user_chats = Chat.objects.filter(user=request.user).select_related('network').prefetch_related(
            'messages').order_by('-updated_at')[:15]

    posts = Post.objects.filter(is_published=True).select_related('category', 'author')
    categories = Category.objects.all()

    category_slug = request.GET.get('category')
    if category_slug:
        category = get_object_or_404(Category, slug=category_slug)
        posts = posts.filter(category=category)

    paginator = Paginator(posts, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'neuro/blog/blog_list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'current_category_slug': category_slug,
        'user_chats': user_chats,
        'current_chat_id': current_chat_id,
    })


def blog_detail(request, slug):
    """Детальная страница статьи"""
    # Получаем чаты пользователя для сайдбара
    user_chats = []
    current_chat_id = None
    if request.user.is_authenticated:
        user_chats = Chat.objects.filter(user=request.user).select_related('network').prefetch_related(
            'messages').order_by('-updated_at')[:15]

    post = get_object_or_404(Post, slug=slug, is_published=True)

    # Увеличиваем счётчик просмотров
    post.views_count += 1
    post.save(update_fields=['views_count'])

    related_posts = Post.objects.filter(category=post.category, is_published=True).exclude(id=post.id)[:3]

    return render(request, 'neuro/blog/blog_detail.html', {
        'post': post,
        'related_posts': related_posts,
        'user_chats': user_chats,
        'current_chat_id': current_chat_id,
    })


def blog_category(request, slug):
    """Страница статей определённой категории"""
    category = get_object_or_404(Category, slug=slug)
    posts = Post.objects.filter(category=category, is_published=True).select_related('category', 'author')
    paginator = Paginator(posts, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    categories = Category.objects.all()
    user_chats = []
    if request.user.is_authenticated:
        user_chats = Chat.objects.filter(user=request.user).select_related('network').prefetch_related('messages').order_by('-updated_at')[:15]
    return render(request, 'neuro/blog/blog_category.html', {
        'category': category,
        'page_obj': page_obj,
        'categories': categories,
        'current_category_slug': slug,
        'user_chats': user_chats,
        'current_chat_id': None,
    })