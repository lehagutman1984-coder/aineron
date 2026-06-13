from .models import Post

def notification_posts(request):
    """Возвращает последние 3 новости с флагом show_in_notification=True"""
    posts = Post.objects.filter(is_published=True, show_in_notification=True).order_by('-published_at')[:3]
    return {'notification_posts': posts}